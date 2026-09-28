# Public demonstration media

[Watch the demo in your browser](https://mohamedzakkaria2004.github.io/Threadline/). The README preview opens this player; release assets remain available for intentional downloads.

This folder contains seven actual application frames, the presentation poster, and the verbatim voiceover captions. Captures use a disposable fictional/public-data store and were reviewed for readable content and absence of credentials/private source material.

The 2:50, 1920×1080 H.264/AAC video is a [v0.3.1 release asset](https://github.com/MohamedZakkaria2004/Threadline/releases/tag/v0.3.1), not a large source-history blob. SHA-256: `5d44eab0e05a9be4f81f3f982b25f6a1d511ea5a5a0b92e0e78e0ccb883f14b9`.

Narration was synthesized locally using Kokoro (`af_heart`). Captions share the exact spoken script and timed audio cues. The video contains no music. Model waits are shortened and labeled; actual inference latency is documented separately in the evaluation guide. Media verification passed 38 checks covering decoding, duration, audio, caption alignment, playback and demonstrated workflow evidence.

Screenshots are unaltered 1440×720 frames from the same actual application recording. Screenshot names describe role/function rather than implying separate production tenants. The hero is illustrative; authenticated screens show backend results.

The original source capture, synthesis models, raw audit outputs and recordings stay in ignored local artifacts. Fonts/model tooling retain their own terms; see [third-party notices](../../THIRD_PARTY_NOTICES.md).

GitHub Pages deploys only the static player and checksum-verified public demo from `scripts/build_demo_site.py`. It does not host the application backend or publish runtime data. The MP4 is fetched from the release during deployment and served as same-origin video media on Pages.
