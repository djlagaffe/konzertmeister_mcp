#!/usr/bin/env python3
"""Read-only GitHub maintenance digest. No model calls, writes, or log downloads."""
import argparse
import json
import re
import subprocess
import sys


def gh(*args):
    return json.loads(subprocess.check_output(['gh', *args], text=True, timeout=45))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', required=True, help='owner/repository; repeat for multiple repos')
    args = parser.parse_args()
    rows = []
    failed = False
    for repo in sorted(set(args.repo)):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            parser.error('invalid repository name')
        try:
            branch = gh('repo', 'view', repo, '--json', 'defaultBranchRef')['defaultBranchRef']['name']
            runs = gh('run', 'list', '--repo', repo, '--branch', branch, '--limit', '30', '--json',
                      'databaseId,workflowName,headSha,status,conclusion,url')
            latest = {}
            for run in runs:
                latest.setdefault(run['workflowName'], run)
            prs = gh('pr', 'list', '--repo', repo, '--limit', '50', '--state', 'open', '--json',
                     'number,title,url,isDraft,author,reviewDecision')
            rows.append({'repository': repo, 'default_branch': branch,
                         'failed_latest_checks': [r for r in latest.values() if r['conclusion'] in
                                                  ['failure', 'timed_out', 'action_required']],
                         'open_prs': prs, 'coverage': 'latest 30 default-branch runs; first 50 open PRs'})
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, KeyError, ValueError):
            failed = True
            rows.append({'repository': repo, 'error': 'GitHub query failed; check gh authentication/access'})
    print(json.dumps(rows, indent=2))
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
