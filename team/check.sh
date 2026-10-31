#!/usr/bin/env bash
# The single quality gate. Fails loudly; never skips silently.
# The architect extends the STACK section once the stack is chosen (tests, linter, type check, dependency audit).
set -uo pipefail
cd "$(dirname "$0")/.."
rc=0
step() { echo; echo "== $*"; }

step "secret files must not be tracked or present in the tree"
found=$(find . \( -name .git -o -name .venv -o -name venv -o -name node_modules -o -name target -o -name .team-state \) -prune -o \( -name '*.p12' -o -name '*.pfx' -o -name '*.pem' -o -name '*.key' -o -name '.env' -o -name '.env.*' \) -print)
if [ -n "$found" ]; then echo "FAIL: secret-like files present:"; echo "$found"; rc=1; else echo "ok"; fi

step "secret patterns in source"
scan_rc=0
# Print paths only; never echo a matching credential into terminal/logs. Ignore dependency/state trees.
grep -rIlE --exclude-dir=.git --exclude-dir=.venv --exclude-dir=venv --exclude-dir=node_modules --exclude-dir=target --exclude-dir=.team-state --exclude-dir=docs --exclude-dir=__pycache__ --exclude=check.sh --exclude='*.p12' --exclude='*.pfx' --exclude='*.pem' --exclude='*.key' --exclude='.env*' \
     -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' -e 'passw(or)?d *= *["'"'"'][^"'"'"']+["'"'"']' . || scan_rc=$?
if [ "$scan_rc" -eq 0 ]; then
  echo "FAIL: possible secret in source (paths above; contents withheld)"; rc=1
elif [ "$scan_rc" -eq 1 ]; then
  echo "ok"
else
  echo "FAIL: source scan could not complete"; rc=1
fi

step "STACK checks"
if [ -f team/stack-check.sh ]; then
  bash team/stack-check.sh || rc=1
else
  echo "FAIL: team/stack-check.sh does not exist yet (architect must create it: tests, lint, types, dependency audit)"
  rc=1
fi

echo; [ $rc -eq 0 ] && echo "CHECK PASSED" || echo "CHECK FAILED"
exit $rc
