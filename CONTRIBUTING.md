# Contributing

Threadline is a bounded local portfolio prototype. Keep changes small, explain the business behavior they affect, and preserve the permission, evidence, and side-effect contracts.

1. Follow [setup](docs/SETUP.md), then work on a feature branch.
2. Use public/synthetic documents and an isolated local data directory for operational tests.
3. For behavior changes, add a regression that verifies intended output/state or a meaningful failure boundary. A valid schema or HTTP 200 alone is insufficient.
4. Run Python/UI tests and the publication check listed below. If model or prompt behavior changes, rerun relevant actual-model gold cases and inspect full answers against original sources.
5. Describe the problem, final behavior, validation, and remaining limitations in the pull request. Do not invent test results or human review judgments.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/ui_state.test.mjs
.\.venv\Scripts\python.exe -m scripts.repository_check
```

Run the publication check again after staging: it scans working files and staged blobs, including ignored files accidentally force-added. Never commit credentials, tokens, runtime databases, vectors, logs, backups, model weights, raw exports or real internal documents. No test requires weakening the normal account/password defaults.

Report security issues through [SECURITY.md](SECURITY.md), not a public issue containing sensitive material. Review the [MIT license](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md) before contributing assets or dependencies.
