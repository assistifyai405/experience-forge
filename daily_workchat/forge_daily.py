"""Local cross-chat Experience Forge adapter. No model calls or networking."""
from __future__ import annotations
import argparse
import os
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
FORGE = ROOT.parent
DATA = Path(os.environ.get('EXPERIENCE_FORGE_DATA_DIR', str(Path.home()/'.local/share/experience-forge')))
sys.path.insert(0, str(FORGE))
from experience_forge.core import canonical, fingerprint


def stamp():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def local_path(value):
    value = str(value).replace('\\', '/')
    if sys.platform == 'win32' and re.match(r'^/mnt/[a-z]/', value):
        value = value[5].upper() + ':' + value[6:]
    elif sys.platform != 'win32' and re.match(r'^[A-Za-z]:/', value):
        value = '/mnt/' + value[0].lower() + value[2:]
    return Path(value).resolve()


def scope(project):
    value = str(local_path(project)).replace('\\', '/')
    if re.match(r'^[A-Za-z]:/', value):
        value = '/mnt/' + value[0].lower() + value[2:]
    return value.casefold() if re.match(r'^/mnt/[a-z]/', value) else value


def evidence(paths):
    result = []
    for value in paths:
        path = local_path(value)
        if not path.is_file():
            raise ValueError(f'Evidence does not exist: {path}')
        result.append({'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()})
    return result


def intact(item):
    payload = {key: value for key, value in item.items() if key not in ('id', 'content_hash')}
    digest = fingerprint(payload)
    return item.get('content_hash') == digest and item.get('id') == 'experience-' + digest[:24]


class Bank:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS experiences(
            id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS usage(
            id INTEGER PRIMARY KEY,created TEXT NOT NULL,project TEXT NOT NULL,
            chat TEXT NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL);''')
        self.db.commit()

    def log(self, project, chat, action, details):
        with self.db:
            self.db.execute('INSERT INTO usage(created,project,chat,action,details) VALUES(?,?,?,?,?)',
                            (stamp(), scope(project), chat, action, canonical(details)))

    def remember(self, project, chat, title, lesson, tags, sources, portable=False):
        if not title.strip() or not lesson.strip() or len(title) > 200 or len(lesson) > 5000:
            raise ValueError('Supply a concise title and actionable lesson')
        if re.search(r'(?i)(sk-[A-Za-z0-9_-]{16,}|github_pat_|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----|(?:password|api[_ -]?key|authorization)\s*[:=]\s*\S+)', title+' '+lesson):
            raise ValueError('Do not store credentials or authentication data')
        if not sources:
            raise ValueError('At least one observed evidence file is required')
        payload = {'project': scope(project), 'chat': chat, 'title': title.strip(),
                   'lesson': lesson.strip(), 'tags': sorted(set(tags)), 'created': stamp(),
                   'portable': bool(portable), 'evidence': evidence(sources),
                   'validation': 'integrity_and_source_snapshot_only'}
        digest = fingerprint(payload)
        item = {'id': 'experience-'+digest[:24], 'content_hash': digest, **payload}
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO experiences VALUES(?,?)',
                            (item['id'], canonical(item)))
        self.log(project, chat, 'remember', {'experience_id': item['id']})
        return item

    def recall(self, project, chat, query, limit=5):
        if not 1 <= limit <= 20:
            raise ValueError('limit must be between 1 and 20')
        tokens = set(re.findall(r'[\w-]+', query.casefold()))
        matches, rejected = [], []
        for row in self.db.execute('SELECT payload FROM experiences'):
            item = json.loads(row[0])
            if not intact(item):
                rejected.append({'id': item.get('id'), 'reason': 'integrity_mismatch'})
                continue
            if item['project'] != scope(project) and not item['portable']:
                continue
            stale = []
            for source in item['evidence']:
                path = local_path(source['path'])
                if not path.is_file() or sha256(path.read_bytes()).hexdigest() != source['sha256']:
                    stale.append(source['path'])
            if stale:
                rejected.append({'id': item['id'], 'reason': 'evidence_changed_or_missing'})
                continue
            text = ' '.join([item['title'], item['lesson'], *item['tags']]).casefold()
            score = sum(token in text for token in tokens)
            if score:
                matches.append((score, item['created'], item))
        matches.sort(key=lambda row: (row[0], row[1], row[2]['id']), reverse=True)
        result = [row[2] for row in matches[:limit]]
        self.log(project, chat, 'recall', {'query': query[:300],
                'experience_ids': [item['id'] for item in result], 'rejected_count': len(rejected)})
        return {'experiences': result, 'rejected': rejected,
                'requires_current_applicability_check': True,
                'authorizes_actions': False, 'model_calls': 0}

    def status(self):
        return {'store': str(self.path),
                'experiences': self.db.execute('SELECT count(*) FROM experiences').fetchone()[0],
                'usage_events': self.db.execute('SELECT count(*) FROM usage').fetchone()[0],
                'chat_count': self.db.execute('SELECT count(DISTINCT chat) FROM usage').fetchone()[0],
                'engine': 'Experience Forge core.canonical/core.fingerprint',
                'engine_sha256': sha256((FORGE/'experience_forge/core.py').read_bytes()).hexdigest(),
                'model_calls': 0, 'network_calls': 0}

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=DATA/'experiences.sqlite3')
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('begin')
    read = sub.add_parser('recall')
    write = sub.add_parser('remember')
    sub.add_parser('status')
    for item in (start, read, write):
        item.add_argument('--project', default=str(Path.cwd()))
        item.add_argument('--chat', required=True)
    start.add_argument('--query', required=True)
    read.add_argument('--query', required=True)
    read.add_argument('--limit', type=int, default=5)
    write.add_argument('--title', required=True)
    write.add_argument('--lesson', required=True)
    write.add_argument('--tag', action='append', default=[])
    write.add_argument('--evidence', action='append', required=True)
    write.add_argument('--portable', action='store_true')
    args = parser.parse_args()
    bank = Bank(args.store)
    try:
        if args.command == 'status': result = bank.status()
        elif args.command in ('begin','recall'):
            result = bank.recall(args.project, args.chat, args.query, getattr(args, 'limit', 5))
            result['habit'] = 'every workchat, independent of project and title'
        else:
            result = bank.remember(args.project,args.chat,args.title,args.lesson,
                                   args.tag,args.evidence,args.portable)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.exit(2, f'Experience Forge: {exc}\n')
    finally:
        bank.close()


if __name__ == '__main__':
    main()
