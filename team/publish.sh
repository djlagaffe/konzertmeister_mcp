#!/usr/bin/env bash
# Create a PRIVATE GitHub repo for this project and push it. Run by the human, not by agents.
#   team/publish.sh [repo-name] [--owner <user-or-org>]
# Defaults: repo name = directory name, owner = the logged-in gh account.
set -euo pipefail
cd "$(dirname "$0")/.."

name=$(basename "$PWD"); owner=""
while [ $# -gt 0 ]; do
  case "$1" in
    --owner) owner=${2:?--owner needs a value}; shift 2 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) name=$1; shift ;;
  esac
done

command -v gh >/dev/null || { echo "gh not installed" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not logged in. Run: gh auth login" >&2; exit 1; }
[ -n "$owner" ] || owner=$(gh api user -q .login)
target="$owner/$name"

[ -d .git ] || git init -q
if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' already set to $(git remote get-url origin); nothing to do." >&2; exit 1
fi
if gh repo view "$target" >/dev/null 2>&1; then
  echo "$target already exists on GitHub; pick another name." >&2; exit 1
fi

# Never publish anything secret-like, whether tracked, staged or merely present.
secrets=$(find . -path ./.git -prune -o \( -name '*.p12' -o -name '*.pfx' -o -name '*.pem' -o -name '*.key' -o -name '.env' -o -name '.env.*' \) -print)
if [ -n "$secrets" ]; then
  echo "Refusing to publish; secret-like files present:" >&2; echo "$secrets" >&2; exit 1
fi

echo "About to create PRIVATE repo $target and push branch '$(git symbolic-ref --short HEAD)'."
echo "Git identity: $(git config user.name) <$(git config user.email)>"
read -r -p "Proceed? [y/N] " ans
[ "$ans" = "y" ] || { echo "Aborted."; exit 1; }

# First commit if the repo has none yet.
if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add -A
  git commit -q -m "Initial commit: project scaffold"
fi

gh repo create "$target" --private --source . --remote origin --push
echo "Done: https://github.com/$target"
