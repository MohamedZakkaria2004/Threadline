# Third-party materials and attribution

- **Manrope:** bundled at `app/static/fonts/Manrope-Variable.ttf`. Copyright and
  SIL Open Font License 1.1 are preserved in
  [OFL-Manrope.txt](app/static/fonts/OFL-Manrope.txt); the adjacent
  [provenance note](app/static/fonts/README.md) records the official source.
- **NIST evaluation documents:** the original public PDFs are used as a small
  reproducible testing corpus, not as project-authored policies. Titles, official
  URLs, editions, hashes and extracted pages are recorded in
  [sources.json](evaluation/audit/sources.json). See the
  [corpus notes](evaluation/audit/README.md) for test provenance. No NIST
  endorsement is implied.
- **Python dependencies:** resolved versions and distribution hashes are in
  `uv.lock`; the tested Windows pip fallback is `requirements.lock.txt`.
  Dependencies retain their respective licenses.
- **Model weights:** not bundled in this repository. Install the configured
  local Qwen and nomic models using Ollama and consult their model terms before
  redistributing weights or a packaged appliance.
- **Demo policies and adversarial fixtures:** fictional, controlled test data.
  They are not real company policies, accounts or secrets.

- **Demonstration narration:** the release video uses locally synthesized Kokoro
  speech (`af_heart`). No voice model weights or synthesis runtime are bundled.
  Upstream project/model terms remain separate from this application's license:
  [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M) and
  [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx).

Original project code, documentation and project-authored demonstration assets
use the [MIT License](LICENSE). This does not relicense the bundled Manrope font,
public NIST documents, dependencies, or separately installed model weights.
No endorsement by a cited source, model publisher, or employer is implied.
