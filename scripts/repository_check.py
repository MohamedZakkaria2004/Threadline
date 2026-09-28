"""Read-only checks of Git's publishable working files AND staged contents.

Uses only the standard library. This is a bounded hygiene check, not a guarantee
that every possible secret can be detected. Values are never printed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIRS = {'.venv', 'venv', '__pycache__', '.pytest_cache', 'data', 'vectors', 'backups', 'snapshots'}
PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.log', '.pid', '.pem', '.key', '.gguf', '.safetensors'}
SECRET_PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'\bAKIA[A-Z0-9]{16}\b|\bsk-proj-[A-Za-z0-9_-]{30,}'),
]
PERSONAL_PATH = re.compile(r'(?i)(?:[a-z]:[/\\]+Users[/\\]+|/(?:Users|home)/)(?!Public\b|<)[\w.-]+')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def candidates(root):
    tracked = set(git(root, 'ls-files', '-z').decode().split('\0')) - {''}
    untracked = set(git(root, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')) - {''}
    return sorted(tracked | untracked), tracked


def inspect_content(name, content, known_secrets=()):
    path = Path(name)
    lower = name.lower()
    reasons = []
    if (any(part.lower() in PRIVATE_DIRS for part in path.parts)
            or (lower.startswith('artifacts/') and lower != 'artifacts/readme.md')
            or (path.name.startswith('.env') and path.name != '.env.example')
            or ('credentials' in path.name.lower() and path.suffix.lower() == '.txt')
            or path.suffix.lower() in PRIVATE_SUFFIXES
            or re.search(r'\.(?:db|sqlite3?)-(?:wal|shm|journal)$', lower)):
        reasons.append('runtime data, environment file, credential or private asset')
    if len(content) > 10 * 1024 * 1024:
        reasons.append('file larger than the 10 MiB source-publication limit')
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        reasons.append('possible credential/private key signature')
    if any(secret and secret in content for secret in known_secrets):
        reasons.append('matches a local demo password')
    # Binary public PDFs/fonts are checked for secret signatures above, not decoded.
    if path.suffix.lower() not in {'.pdf', '.ttf', '.png', '.jpg', '.ico'}:
        if PERSONAL_PATH.search(content.decode('utf-8', errors='replace')):
            reasons.append('personal absolute filesystem path')
    return reasons


def check(root, known_secrets=()):
    names, tracked = candidates(root)
    issues = []
    for name in names:
        path = root / name
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            issues.append({'file': name, 'problem': 'link/junction requires explicit review'})
            continue
        if not path.is_file():
            issues.append({'file': name, 'problem': 'indexed file is missing from the working tree'})
            continue
        copies = [('working', path.read_bytes())]
        if name in tracked:
            copies.append(('index', git(root, 'show', ':' + name)))
        for location, content in copies:
            issues.extend({'file': name, 'version': location, 'problem': reason}
                          for reason in inspect_content(name, content, known_secrets))
        if path.suffix.lower() == '.md':
            text = path.read_text(encoding='utf-8')
            for target in re.findall(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)', text):
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                target = target.split('#', 1)[0]
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(root.resolve()) or resolved.relative_to(root.resolve()).as_posix() not in names:
                    issues.append({'file': name, 'problem': 'local link target is not in the publication set', 'target': target})
    source_manifest = root / 'evaluation/audit/sources.json'
    if source_manifest.exists():
        manifest = json.loads(source_manifest.read_text(encoding='utf-8'))
        entries = manifest if isinstance(manifest, list) else manifest['sources']
        for entry in entries:
            source = source_manifest.parent / entry['filename']
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
                issues.append({'file': source.name, 'problem': 'public source bytes do not match recorded SHA-256'})
    evidence_manifest = root / 'docs/evidence/manifest.json'
    if evidence_manifest.exists():
        for entry in json.loads(evidence_manifest.read_text(encoding='utf-8')):
            source = evidence_manifest.parent / entry['file']
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
                issues.append({'file': source.name, 'problem': 'historical evidence bytes do not match recorded SHA-256'})
    return {'status': 'FAIL' if issues else 'PASS', 'files_checked': len(names),
            'tracked_files_checked_in_index': len(tracked), 'issues': issues,
            'scope': 'Current working tree and Git index; prior commit history is not scanned.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path, help='Optional local generated demo password file; values are never printed.')
    args = parser.parse_args()
    known_secrets = []
    if args.credentials_file:
        text = args.credentials_file.read_text(encoding='utf-8')
        known_secrets = [value.encode() for value in re.findall(r'^(?:employee|hr|manager|admin): (\S+)', text, re.M)]
        if len(known_secrets) != 4:
            parser.error('Expected exactly four generated demo account entries.')
    result = check(ROOT, known_secrets)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
