"""Local server entry point. One worker owns the embedded vector store."""
import os
import socket
import uvicorn
from .config import Settings
from .config import ROOT
from .main import create_app

if __name__ == "__main__":
    settings = Settings()
    port = int(os.getenv("COPILOT_PORT", "8765"))
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"Port {port} is already in use. Atlas may already be running at http://127.0.0.1:{port}. Stop the existing process before starting another instance.", flush=True)
            raise SystemExit(0)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "server.pid").write_text(str(os.getpid()), encoding="ascii")
    print(f"Atlas: http://127.0.0.1:{port}", flush=True)
    print(f"Demo credentials: {settings.data_dir / 'demo-credentials.txt'}", flush=True)
    uvicorn.run(create_app(settings), host="127.0.0.1", port=port, workers=1, log_level="info")
