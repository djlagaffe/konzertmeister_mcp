#!/usr/bin/env python3
"""Local task checkpoints and measurements. No model calls or transcript storage."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


@contextmanager
def database():
    state = ROOT / '.team-state'
    state.mkdir(mode=0o700, exist_ok=True)
    with sqlite3.connect(state / 'tasks.sqlite', timeout=10) as db:
        db.execute('CREATE TABLE IF NOT EXISTS steps (task TEXT, step TEXT, fingerprint TEXT, '
                   'status TEXT, failures INTEGER, seconds REAL, rc INTEGER, PRIMARY KEY(task,step,fingerprint))')
        db.execute('CREATE TABLE IF NOT EXISTS outcomes (task TEXT, model TEXT, outcome TEXT, '
                   'input_tokens INTEGER, output_tokens INTEGER, seconds REAL, at REAL)')
        columns = {row[1] for row in db.execute('PRAGMA table_info(outcomes)')}
        for name in ('first_runnable_seconds', 'tool_calls', 'retries'):
            if name not in columns:
                db.execute(f'ALTER TABLE outcomes ADD COLUMN {name} REAL')
        db.commit()
        db.execute('CREATE TABLE IF NOT EXISTS worktrees (task TEXT PRIMARY KEY, path TEXT, branch TEXT)')
        yield db


def run(args):
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise ValueError('a command is required after --')
    fingerprint = hashlib.sha256(json.dumps(command).encode()).hexdigest()
    key = (args.task, args.step, fingerprint)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT status,failures FROM steps WHERE task=? AND step=? AND fingerprint=?', key).fetchone()
        if row and (args.once or row[0] == 'running' or row[1] >= 2):
            raise ValueError('checkpoint blocks replay: inspect the result; use resolve only after verifying state/approval')
        db.execute('INSERT OR REPLACE INTO steps VALUES (?,?,?,?,?,?,?)',
                   (*key, 'running', row[1] if row else 0, 0, None))
    start = time.monotonic()
    try:
        rc = subprocess.run(command, cwd=ROOT, timeout=args.timeout).returncode
    except subprocess.TimeoutExpired:
        rc = 124
    except KeyboardInterrupt:
        rc = 130
    except OSError:
        rc = 127
    elapsed = time.monotonic() - start
    with database() as db:
        db.execute('UPDATE steps SET status=?,failures=CASE WHEN ?=0 THEN 0 ELSE failures+1 END,seconds=?,rc=? '
                   'WHERE task=? AND step=? AND fingerprint=?',
                   ('passed' if rc == 0 else 'failed', rc, elapsed, rc, *key))
    print(f'checkpoint: {args.task}/{args.step} rc={rc} seconds={elapsed:.2f}', file=sys.stderr)
    return rc


def worktree(args):
    if git('rev-parse', '--is-inside-work-tree') != 'true':
        raise ValueError('worktree requires a Git repository')
    suffix = hashlib.sha256(args.task.encode()).hexdigest()[:12]
    branch = 'maintenance/' + suffix
    path = ROOT.parent / '.herdr-worktrees' / ROOT.name / suffix
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT path,branch FROM worktrees WHERE task=?', (args.task,)).fetchone()
        if row:
            registered = git('worktree', 'list', '--porcelain').splitlines()
            if f'worktree {row[0]}' not in registered or not Path(row[0]).is_dir():
                raise ValueError('recorded worktree is missing; inspect Git worktree state')
            print(row[0])
            return 0
        # If a crash occurred between git worktree add and the DB commit, refuse to duplicate it.
        if path.exists() or subprocess.run(['git', '-C', str(ROOT), 'show-ref', '--verify', '--quiet',
                                         'refs/heads/' + branch]).returncode == 0:
            raise ValueError('worktree/branch already exists without a checkpoint; inspect before recovery')
        git('rev-parse', '--verify', args.base + '^{commit}')
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '-b', branch, str(path), args.base], check=True, stdout=sys.stderr)
        db.execute('INSERT INTO worktrees VALUES (?,?,?)', (args.task, str(path), branch))
    print(path)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('run'); p.add_argument('task'); p.add_argument('step')
    p.add_argument('--once', action='store_true'); p.add_argument('--timeout', type=int, default=600)
    p = sub.add_parser('worktree'); p.add_argument('task'); p.add_argument('--base', default='HEAD')
    p = sub.add_parser('resolve'); p.add_argument('task'); p.add_argument('step')
    p.add_argument('--verified', action='store_true', required=True)
    p = sub.add_parser('handoff'); p.add_argument('task'); p.add_argument('--next', required=True)
    p.add_argument('--checks', default='not recorded'); p.add_argument('--failed', default='none recorded')
    p.add_argument('--approved', default='none; ask before switching models or paid delegation')
    p = sub.add_parser('record'); p.add_argument('task'); p.add_argument('--model', required=True)
    p.add_argument('--outcome', choices=['accepted', 'rejected', 'blocked'], required=True)
    for name in ('input-tokens', 'output-tokens', 'tool-calls', 'retries'):
        p.add_argument('--' + name, type=int)
    p.add_argument('--seconds', type=float)
    p.add_argument('--first-runnable-seconds', type=float)
    sub.add_parser('summary')
    args, extra = parser.parse_known_args()
    if args.action == 'run':
        args.command = extra
        if args.timeout <= 0: parser.error('timeout must be positive')
    elif extra:
        parser.error('unrecognized arguments: ' + ' '.join(extra))
    if hasattr(args, 'task') and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/#-]{0,127}', args.task):
        parser.error('task must be a short identifier, e.g. issue-42 or owner/repo#42')
    for field in ('input_tokens', 'output_tokens', 'seconds', 'first_runnable_seconds', 'tool_calls', 'retries'):
        value = getattr(args, field, None)
        if value is not None and value < 0:
            parser.error('measurements cannot be negative')
    try:
        if args.action == 'handoff':
            fields = [args.next, args.checks, args.failed, args.approved]
            if any('\n' in v or len(v) > 500 for v in fields):
                raise ValueError('handoff fields must be single lines, at most 500 characters; link detailed evidence')
            status = git('status', '--short').splitlines()
            text = ['# Handoff', '', 'Commit: ' + git('rev-parse', 'HEAD'),
                    'Branch: ' + git('branch', '--show-current'), 'Task: ' + args.task,
                    'Checks: ' + args.checks, 'Failed approaches: ' + args.failed,
                    'Model approval: ' + args.approved, 'Next: ' + args.next, '', 'Changed paths:']
            text += status[:30]
            if len(status) > 30: text.append(f'... {len(status)-30} more; inspect git status')
            dest = ROOT / 'docs/handoff.md'; dest.parent.mkdir(exist_ok=True)
            temp = dest.with_suffix('.tmp'); temp.write_text('\n'.join(text) + '\n'); temp.replace(dest)
            print(dest)
            return 0
        if args.action == 'run': return run(args)
        if args.action == 'worktree': return worktree(args)
        with database() as db:
            if args.action == 'resolve':
                db.execute('DELETE FROM steps WHERE task=? AND step=?', (args.task, args.step))
                print('checkpoint cleared after operator verification; check external state before retrying')
            elif args.action == 'record':
                db.execute('INSERT INTO outcomes (task,model,outcome,input_tokens,output_tokens,seconds,at,first_runnable_seconds,tool_calls,retries) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (args.task, args.model, args.outcome, args.input_tokens, args.output_tokens, args.seconds,
                            time.time(), args.first_runnable_seconds, args.tool_calls, args.retries))
            else:
                rows = db.execute('SELECT model,outcome,COUNT(*),SUM(input_tokens),SUM(output_tokens),SUM(seconds) '
                                  ' ,AVG(first_runnable_seconds),SUM(tool_calls),SUM(retries) FROM outcomes GROUP BY model,outcome').fetchall()
                print(json.dumps({'outcomes': [dict(zip(['model','outcome','tasks','input_tokens','output_tokens','seconds','mean_first_runnable_seconds','tool_calls','retries'], r))
                                               for r in rows], 'steps': db.execute('SELECT COUNT(*) FROM steps').fetchone()[0]}, indent=2))
        return 0
    except (ValueError, subprocess.CalledProcessError, sqlite3.Error) as exc:
        print(f'task: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
