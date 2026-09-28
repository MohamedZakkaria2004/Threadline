"""Run once with the web application stopped. Uses only installed local models."""
import json
from app.config import ROOT, Settings
from app.storage import Store
from app.llm import Ollama
from app.knowledge import Knowledge


def main():
    settings = Settings()
    store = Store(settings.data_dir / "copilot.db")
    llm = Ollama(settings, store)
    try:
        knowledge = Knowledge(settings, store, llm)
    except RuntimeError as exc:
        llm.close()
        raise SystemExit("Cannot open the local vector store. Stop Atlas before running the seed command.") from exc
    try:
        store.recover_interrupted()
        health = llm.health()
        if not health["ready"]:
            raise SystemExit("Start Ollama and install the configured models before seeding: " + ", ".join(health["missing"]))
        corpus = ROOT / "sample_docs"
        manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8-sig"))
        for entry in manifest:
            result = knowledge.ingest(entry["filename"], (corpus / entry["filename"]).read_bytes(), entry["classification"], "admin", title=entry["title"], department=entry["department"])
            print(f"{'Exists' if result.get('duplicate') else 'Indexed'}: {result['title']} ({result['chunk_count']} chunks)", flush=True)
        print("Demo credentials: " + str(settings.data_dir / "demo-credentials.txt"))
    finally:
        knowledge.close()
        llm.close()


if __name__ == "__main__":
    main()
