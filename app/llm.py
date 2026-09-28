import hashlib
import json
import time
import math
from pathlib import Path
import httpx
from pydantic import ValidationError
from .config import ROOT
from .storage import now


class ModelUnavailable(RuntimeError):
    pass


class Ollama:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.client = httpx.Client(base_url=settings.ollama_url, timeout=httpx.Timeout(240, connect=5), trust_env=False)

    def health(self):
        try:
            response = self.client.get("/api/tags", timeout=5)
            response.raise_for_status()
            entries = response.json().get("models", [])
            models = [item["name"] for item in entries]
            missing = [m for m in [self.settings.model, self.settings.embed_model] if m not in models]
            return {"connected": True, "ready": not missing, "models": models, "missing": missing, "digests": {item['name']: item.get('digest') for item in entries}}
        except httpx.TimeoutException:
            return {"connected": False, "ready": False, "models": [], "missing": [], "error": "The local model status check timed out. It may be busy; retry the status check."}
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return {"connected": False, "ready": False, "models": [], "missing": [], "error": "Could not reach a valid Ollama endpoint. Start Ollama, then retry the status check."}

    def identity(self):
        state = self.health()
        digests = {name: state.get('digests', {}).get(name) for name in (self.settings.model, self.settings.embed_model)}
        if not state['ready'] or any(not isinstance(value, str) or not value for value in digests.values()):
            raise ModelUnavailable('Installed model fingerprints are unavailable. Check local Ollama before evaluating.')
        return digests

    def embed(self, texts, query=False):
        prefix = "search_query: " if query else "search_document: "
        inputs = [prefix + t if "nomic" in self.settings.embed_model else t for t in texts]
        try:
            response = self.client.post("/api/embed", json={"model": self.settings.embed_model, "input": inputs, "truncate": False, "keep_alive": "5m"})
            response.raise_for_status()
            vectors = response.json()["embeddings"]
            if len(vectors) != len(texts) or not all(vectors) or len({len(v) for v in vectors}) != 1 or any(not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v) or sum(x*x for x in v) == 0 for v in vectors):
                raise ValueError("Embedding count mismatch")
            return vectors
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise ModelUnavailable("Local embedding failed. Check Ollama and the installed embedding model.") from exc

    def structured(self, messages, schema, operation, user_id=None, workflow_id=None):
        started, status, data = time.perf_counter(), "error", {}
        try:
            response = self.client.post("/api/chat", json={
                "model": self.settings.model, "messages": messages, "stream": False,
                "format": schema.model_json_schema(), "keep_alive": "5m", "think": False,
                "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 450},
            })
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                data = {}
                raise ValueError("Expected an object from the local model.")
            result = schema.model_validate_json(data["message"]["content"])
            status = "ok"
            return result
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise ModelUnavailable("The local model did not return a valid response. Check Ollama, then retry.") from exc
        finally:
            latency = (time.perf_counter() - started) * 1000
            energy = latency / 3_600_000 * self.settings.power_watts / 1000 * self.settings.electricity_usd_kwh
            self.store.run("INSERT INTO metrics(workflow_id,user_id,operation,latency_ms,prompt_tokens,output_tokens,model,prompt_version,status,estimated_energy_usd,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (workflow_id, user_id, operation, latency, data.get("prompt_eval_count", 0), data.get("eval_count", 0), self.settings.model, self.settings.prompt_version, status, energy, now()))

    def close(self):
        self.client.close()


def prompt(name, version):
    return (ROOT / "prompts" / version / f"{name}.txt").read_text(encoding="utf-8")


def prompt_inventory():
    return [{"version": p.parent.name, "name": p.stem, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "content": p.read_text(encoding="utf-8")} for p in sorted((ROOT / "prompts").glob("*/*.txt"))]
