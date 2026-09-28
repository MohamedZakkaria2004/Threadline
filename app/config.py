from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import os
import math

ROOT = Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / ("EnterpriseCopilot" if os.name == "nt" else "enterprise-copilot")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("COPILOT_DATA_DIR", str(default_data_dir()))))
    model: str = field(default_factory=lambda: os.getenv("COPILOT_MODEL", "qwen3:4b-instruct-2507-q4_K_M"))
    embed_model: str = field(default_factory=lambda: os.getenv("COPILOT_EMBED_MODEL", "nomic-embed-text:latest"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    prompt_version: str = field(default_factory=lambda: os.getenv("COPILOT_PROMPT_VERSION", "v4"))
    power_watts: float = field(default_factory=lambda: float(os.getenv("COPILOT_POWER_WATTS", "100")))
    electricity_usd_kwh: float = field(default_factory=lambda: float(os.getenv("COPILOT_ELECTRICITY_USD_KWH", "0.15")))

    def __post_init__(self):
        parsed = urlparse(self.ollama_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password:
            raise ValueError("Ollama must use a loopback HTTP URL. Hosted inference is disabled.")
        if "cloud" in self.model.lower() or "cloud" in self.embed_model.lower():
            raise ValueError("Cloud models are disabled. Choose an installed local model.")
        if self.prompt_version not in {"v1", "v2", "v3", "v4"}:
            raise ValueError("Prompt version must be v1, v2, v3 or v4.")
        if not math.isfinite(self.power_watts) or not math.isfinite(self.electricity_usd_kwh) or self.power_watts < 0 or self.electricity_usd_kwh < 0:
            raise ValueError("Cost assumptions cannot be negative.")
        self.data_dir.mkdir(parents=True, exist_ok=True)
