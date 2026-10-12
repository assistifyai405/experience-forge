"""Bounded publication audit of text files and nested evidence archives; no network."""
import argparse
import json
from pathlib import Path
import re
import zipfile

TEXT = {'.py', '.md', '.json', '.jsonl', '.yml', '.yaml', '.cff', '.html', '.cmd', '.sh', '.cjs', '.log', '.sha256'}
PATTERNS = {
    'personal_home_path': re.compile(r'(?:/mnt/[a-z]/Users/[^/\s"<>]+/|[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s"<>]+[\\/])'),
    'github_token_shape': re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'),
    'provider_key_shape': re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'),
    'private_key_block': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential_assignment': re.compile(r'''(?i)(?:api[_-]?key|password|access[_-]?token|secret)\s*[=:]\s*["']([A-Za-z0-9_./+\-]{20,})["']'''),
}


def audit_items(items, denied):
    checked = 0
    issues = []
    for name, data in items:
        basename = Path(name).name
        if basename.startswith('.env') and basename != '.env.example':
            issues.append({'file': name, 'check': 'environment_file_not_for_publication'})
        if Path(name).suffix.lower() not in TEXT and basename not in {'README', 'LICENSE', '.gitignore', '.gitattributes'} and not basename.startswith('.env'):
            continue
        text = data.decode('utf-8', errors='strict')
        checked += 1
        for key, pattern in PATTERNS.items():
            if pattern.search(text):
                issues.append({'file': name, 'check': key})
        for value in denied:
            if value and value.casefold() in text.casefold():
                issues.append({'file': name, 'check': 'explicitly_denied_private_value'})
        if Path(name).suffix == '.json':
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                issues.append({'file': name, 'check': 'invalid_json'})
                continue
            def inspect(value):
                if isinstance(value, dict):
                    if any(k in value for k in ('credential_present', 'credential_source', 'hostname', 'probe_host')):
                        issues.append({'file': name, 'check': 'workstation_or_credential_presence_metadata'})
                    for item in value.values(): inspect(item)
                elif isinstance(value, list):
                    for item in value: inspect(item)
            inspect(payload)
    if issues:
        # Never emit a matched secret or private value.
        raise ValueError(json.dumps({'issues': issues}, indent=2))
    return checked


def archive_items(path):
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                yield info.filename, archive.read(info)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--deny-value', action='append', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.archive:
        checked = audit_items(archive_items(args.archive), args.deny_value)
    else:
        paths = [p for p in root.rglob('*') if p.is_file() and not any(part in {'.git', '__pycache__', '.publication-work'} for part in p.relative_to(root).parts)]
        checked = audit_items(((str(p.relative_to(root)), p.read_bytes()) for p in paths), args.deny_value)
        for path in paths:
            if path.suffix == '.zip':
                checked += audit_items(archive_items(path), args.deny_value)
    print(json.dumps({'text_files_checked': checked, 'pattern_issues': 0,
        'limits': 'Pattern audit and selected private-value checks, not a guarantee against every possible secret.'}, indent=2))


if __name__ == '__main__':
    main()
