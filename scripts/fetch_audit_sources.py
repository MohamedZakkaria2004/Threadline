"""Download the two fixed official NIST documents; retain originals and provenance."""
import hashlib
import json
from pathlib import Path
import httpx
from app.config import ROOT
from app.knowledge import extract_sections
from app.storage import now

SOURCES = [
    ('nist-csf-1300.pdf', 'https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf', 'NIST SP 1300: Small Business Quick-Start Guide', 'February 2024', 9),
    ('nist-phishing.pdf', 'https://www.nist.gov/document/sbccphishingpdf', 'NIST Small Business Fact Sheet: Phishing', 'March 2024', 2),
]
PINNED = {
 'nist-csf-1300.pdf':'1e77c1bd63d1e15c48c870b7c17b7c9a2edf6bd5103b0940e72828515c9f1881',
 'nist-phishing.pdf':'48f39cfbc0372a2146935d12ff76cb7c4903bfca664c5c5b961fdf7d60a67526',
}

def main():
    target = ROOT / 'evaluation' / 'audit'
    target.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client(timeout=60, follow_redirects=True, trust_env=False) as client:
        for filename, url, title, edition, pages in SOURCES:
            path = target / filename
            if not path.exists():
                response = client.get(url)
                response.raise_for_status()
                assert response.content.startswith(b'%PDF'), 'Expected original PDF'
                path.write_bytes(response.content)
            content = path.read_bytes()
            assert hashlib.sha256(content).hexdigest()==PINNED[filename], 'Official source changed; review and deliberately re-freeze ground truth before proceeding.'
            sections = extract_sections(filename, content)
            assert len(sections) == pages
            (target / (filename + '.extracted.json')).write_text(json.dumps(sections, indent=2), encoding='utf-8')
            records.append(dict(filename=filename, url=url, title=title, edition=edition,
                                sha256=hashlib.sha256(content).hexdigest(), bytes=len(content), pages=pages,
                                retrieved_at=now(), provenance='Original official US government PDF; no content edits.'))
    (target / 'sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps(records, indent=2))

if __name__ == '__main__':
    main()
