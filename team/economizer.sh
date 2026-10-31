#!/usr/bin/env bash
# Opt-in, pinned, project-local TokenEconomizer pilot. No global plugin install.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
dir=${ECONOMIZER_DIR:-$root/../tools/TokenEconomizer}
pin=e428fc91b0f8ffecb5a596d56b14fe2f1485a5f9
[ -f "$dir/plugin/scripts/te" ] && [ "$(git -C "$dir" rev-parse HEAD)" = "$pin" ] || {
  echo "Expected TokenEconomizer $pin at $dir. Set ECONOMIZER_DIR to the reviewed checkout." >&2; exit 1;
}
export TOKENECONOMIZER_HOME="$root/.team-state/tokeneconomizer"
export TE_MICROSKILLS=envfacts TE_TOOLPRUNE=propose TE_LOOPGUARD=off TE_REPOMAP=off
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN OPENAI_API_KEY CODEX_API_KEY
case "${1:-status}" in
  status) exec "$dir/plugin/scripts/te" --host claude --cwd "$root" status ;;
  setup) exec "$dir/plugin/scripts/te" --host claude --cwd "$root" config set microskills=envfacts toolprune=propose loopguard=off repomap=off ;;
  start) shift; export TEAM_ECONOMIZER_DIR="$dir"; exec bash "$root/team/start.sh" "$@" ;;
  claude) shift; cd "$root"; exec claude --plugin-dir "$dir/plugin" "$@" ;;
  *) echo 'usage: team/economizer.sh [setup|status|start [--no-local]|claude [args...]]' >&2; exit 2 ;;
esac
