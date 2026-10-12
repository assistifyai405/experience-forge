"""Verify the unchanged captured pilot from its bundled ZIP. Standard library only."""
from hashlib import sha256
import json
from pathlib import Path
import socket
import stat
import sys
import tempfile
from unittest.mock import patch
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from experience_forge.reuse_benchmark import verify_reuse


def deny_network(*args, **kwargs):
    raise AssertionError('Network connection attempted during captured-evidence verification')


def main():
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Exact captured replay requires Python 3.14, matching the recorded aggregate arithmetic. The daily adapter and unit tests support Python 3.11+. No evidence is modified.")
    checksums = json.loads((root / 'evidence/checksums.json').read_text(encoding='utf-8'))
    archive = root / 'evidence/reuse-complete.zip'
    if set(checksums) != {'reuse-complete.zip'} or sha256(archive.read_bytes()).hexdigest() != checksums['reuse-complete.zip']:
        raise ValueError('Bundled evidence ZIP fingerprint differs')
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(archive) as bundle:
        names = [info.filename for info in bundle.infolist()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate evidence entry')
        if sum(info.file_size for info in bundle.infolist()) > 50_000_000:
            raise ValueError('Unexpected expanded evidence size')
        for info in bundle.infolist():
            parts = Path(info.filename).parts
            if len(parts) != 2 or parts[0] != 'reuse-complete' or '..' in parts or Path(info.filename).is_absolute() or '\\' in info.filename:
                raise ValueError('Unexpected evidence path')
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Evidence links are prohibited')
        bundle.extractall(temp)
        with patch.object(socket.socket, 'connect', deny_network), patch.object(socket.socket, 'connect_ex', deny_network):
            result = verify_reuse(Path(temp) / 'reuse-complete')
    if result['new_model_calls'] or result['new_remote_requests']:
        raise ValueError('Verification must not make new inference or network calls')
    review = root / 'reviews/jev-prompt-20261012'
    for name, digest in json.loads((review / 'manifest.json').read_text(encoding='utf-8')).items():
        if Path(name).name != name or sha256((review / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Public design-review evidence differs')
    original = json.loads((review / 'result.json').read_text(encoding='utf-8'))
    metrics = json.loads((review / 'metrics.json').read_text(encoding='utf-8'))
    if original['model'] != 'jev-1.13.0' or original['isError'] or metrics['provider_requests'] != 1:
        raise ValueError('Design review model/provider accounting differs')
    if len(original['answers']) != 3 or original['usage']['input_tokens'] != metrics['input_tokens'] or original['usage']['output_tokens'] != metrics['output_tokens']:
        raise ValueError('Design review answer/usage accounting differs')
    print(json.dumps({'captured_pilot': result, 'review': 'one previously authorized paid review; no new calls',
        'experimental_source_unchanged': True, 'python_network_connections_denied': True}, indent=2))


if __name__ == '__main__':
    main()
