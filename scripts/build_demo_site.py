"""Build only the public demo player and checksum-verified release media.

No application code, runtime data, credentials or model weights enter the site.
The MP4 stays out of source history and is fetched only during a site build.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VIDEO_NAME = 'Threadline-Enterprise-Demo.mp4'
VIDEO_URL = 'https://github.com/MohamedZakkaria2004/Threadline/releases/download/v0.3.1/' + VIDEO_NAME
VIDEO_SHA256 = '5d44eab0e05a9be4f81f3f982b25f6a1d511ea5a5a0b92e0e78e0ccb883f14b9'
PUBLIC_ASSETS = {
    'demo/index.html': 'index.html',
    'demo/styles.css': 'styles.css',
    'docs/media/demo-poster.jpg': 'poster.jpg',
    'app/static/fonts/Manrope-Variable.ttf': 'Manrope-Variable.ttf',
    'app/static/fonts/OFL-Manrope.txt': 'OFL-Manrope.txt',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, help='Use an existing local copy of the verified demo instead of downloading it.')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/demo-site')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit('Use a new or empty output directory to avoid publishing leftover files.')
    if args.video:
        video = args.video.read_bytes()
    else:
        request = urllib.request.Request(VIDEO_URL, headers={'User-Agent': 'Threadline-demo-builder'})
        with urllib.request.urlopen(request, timeout=120) as response:
            video = response.read(25 * 1024 * 1024)
    if hashlib.sha256(video).hexdigest() != VIDEO_SHA256:
        raise SystemExit('Demo checksum mismatch. Refusing to publish unverified video.')
    args.output.mkdir(parents=True, exist_ok=True)
    for source, destination in PUBLIC_ASSETS.items():
        shutil.copyfile(ROOT / source, args.output / destination)
    (args.output / VIDEO_NAME).write_bytes(video)
    (args.output / '.nojekyll').write_text('', encoding='utf-8')
    print(f'Built public demo player: {len(PUBLIC_ASSETS) + 2} files; verified {len(video)} video bytes.')


if __name__ == '__main__':
    main()
