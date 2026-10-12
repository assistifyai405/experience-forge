"""Check local Markdown and standalone viewer links; no HTTP requests."""
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

root = Path(__file__).resolve().parents[1]
checked = 0
failures = []
paths = [p for p in root.rglob('*.md') if not any(part in {'.git', '__pycache__', '.publication-work', 'history', 'runs'} for part in p.relative_to(root).parts)]
paths += [root / 'reports/reuse-viewer/index.html']
for path in paths:
    text = path.read_text(encoding='utf-8')
    links = re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text) if path.suffix == '.md' else re.findall(r'(?:href|src)="([^"]+)"', text)
    for target in links:
        target = target.strip('<>')
        if urlparse(target).scheme or target.startswith(('#', '//')):
            continue
        name = unquote(target.split('#', 1)[0].split('?', 1)[0])
        if not name:
            continue
        destination = (path.parent / name).resolve()
        checked += 1
        if not destination.is_relative_to(root) or not destination.exists():
            failures.append({'file': str(path.relative_to(root)), 'target': target})
if failures:
    raise SystemExit(json.dumps({'broken_local_links': failures}, indent=2))
print(json.dumps({'local_links_checked': checked, 'broken': 0, 'remote_links_fetched': 0}, indent=2))
