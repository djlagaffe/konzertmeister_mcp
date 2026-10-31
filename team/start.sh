#!/usr/bin/env bash
# Launch the team in Herdr: lead (Claude) | reviewer (Codex) | shell for checks.
# Run from inside Herdr (or any terminal; it then creates the workspace in the running session).
#   team/start.sh              normal start; adds the local-model pane if Ollama is reachable
#   team/start.sh --no-local   never add the local pane
# Env: LEAD_CONTINUE=1 resumes Lead's previous conversation in this folder; LEAD_MODEL (default sonnet), REVIEWER_EFFORT (default low), OLLAMA_URL, OLLAMA_MODEL
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
want_local=1
case "${1:-}" in
  --no-local) want_local=0 ;;
  ""|--local) ;;
  *) echo "usage: team/start.sh [--no-local]" >&2; exit 2 ;;
esac
confirm() {
  local answer
  printf '%s [y/N] ' "$1" >&2
  if ! read -r answer || [[ ! "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Not approved; stopping before starting agents." >&2
    exit 1
  fi
}
ollama_url= ollama_model=
if [ "$want_local" = 1 ]; then
  discovery=$(bash "$root/team/ollama-discover.sh")
  ollama_url=$(jq -r '.url // empty' <<<"$discovery")
  preferred=${OLLAMA_MODEL:-qwen2.5-coder:7b}
  if jq -e --arg m "$preferred" '.models | index($m) != null' <<<"$discovery" >/dev/null; then
    ollama_model=$preferred
  elif [ "$(jq '.models | length' <<<"$discovery")" -gt 0 ]; then
    echo "Installed local models:" >&2
    jq -r '.models[]' <<<"$discovery" >&2
    printf 'Preferred model %s is absent. Enter an installed model to approve it (blank cancels): ' "$preferred" >&2
    read -r ollama_model || exit 1
    jq -e --arg m "$ollama_model" '.models | index($m) != null' <<<"$discovery" >/dev/null || { echo "No installed model approved." >&2; exit 1; }
  else
    want_local=0
    confirm "No installed local Ollama models found. Continue with subscription agents and request approval before paid task routing?"
  fi
fi
printf 'Models: lead=%s; reviewer=Codex subscription; local=%s\n' "${LEAD_MODEL:-sonnet}" "${ollama_model:-disabled}"

lead_model=${LEAD_MODEL:-sonnet}
reviewer_effort=${REVIEWER_EFFORT:-low}

"$root/team/preflight.sh"

# Subscription auth only, whatever the parent environment says.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN OPENAI_API_KEY CODEX_API_KEY

label=$(basename "$root")
ws=$(herdr workspace create --cwd "$root" --label "$label" --focus)
lead=$(jq -er '.result.root_pane.pane_id' <<<"$ws")

reviewer=$(herdr pane split "$lead" --direction right --cwd "$root" --no-focus | jq -er '.result.pane.pane_id')
shell=$(herdr pane split "$reviewer" --direction down --cwd "$root" --no-focus | jq -er '.result.pane.pane_id')

# A fresh pane's shell may not be at its prompt yet; retry instead of dying half-way.
start_agent() {
  local name=$1; shift
  for attempt in 1 2 3 4 5; do
    sleep 2
    herdr agent start "$name" "$@" >/dev/null && return 0
    echo "agent start '$name' failed (attempt $attempt), retrying..." >&2
  done
  echo "could not start agent '$name'" >&2; return 1
}
lead_args=(--model "$lead_model"); [ "${LEAD_CONTINUE:-0}" = 1 ] && lead_args+=(--continue)
if [ -n "${TEAM_ECONOMIZER_DIR:-}" ]; then
  # Enabled explicitly by team/economizer.sh; keep all auxiliary model calls off.
  lead_args+=(--plugin-dir "$TEAM_ECONOMIZER_DIR/plugin")
  printf -v lead_env 'export TOKENECONOMIZER_HOME=%q TE_MICROSKILLS=envfacts TE_TOOLPRUNE=propose TE_LOOPGUARD=off TE_REPOMAP=off' "$root/.team-state/tokeneconomizer"
  herdr pane run "$lead" "$lead_env" >/dev/null
fi
start_agent lead     --kind claude --pane "$lead" -- "${lead_args[@]}"
start_agent reviewer --kind codex  --pane "$reviewer" -- -c "model_reasoning_effort=\"$reviewer_effort\""

if [ "$want_local" = 1 ]; then
  local_pane=$(herdr pane split "$shell" --direction down --cwd "$root" --no-focus | jq -er '.result.pane.pane_id')
  herdr pane rename "$local_pane" "local" >/dev/null
  printf -v local_env 'export CODEX_OSS_BASE_URL=%q' "$ollama_url/v1"
  herdr pane run "$local_pane" "$local_env" >/dev/null
  # Cheap helper for low-stakes work. Never for security review (see AGENTS.md).
  start_agent local --kind codex --pane "$local_pane" -- --oss --local-provider ollama -m "$ollama_model"
fi

herdr pane rename "$shell" "checks" >/dev/null
herdr pane run "$shell" "echo 'quality gate: team/check.sh'" >/dev/null

# The reviewer is not pre-briefed (saves paid tokens); Lead's tasks tell it to read its charter.
[ "$want_local" = 1 ] && herdr agent prompt local "Caveman mode: few words, full meaning; preserve exact technical content and uncertainty. Read team/roles/local.md. Reply with one line, then wait for tasks." >/dev/null
herdr agent prompt lead "Caveman mode. Read AGENTS.md; run bash team/capabilities.sh. Local model: ${ollama_model:-none}; endpoint: ${ollama_url:-none}. Read docs/handoff.md if present and validate its commit/worktree; otherwise relevant docs/03-plan.md sections. Resume completed work. Choose maintenance, small runnable slice or architecture/risky path. Deliver something runnable early; load team/process.md only when risk/architecture requires it. Ask before switching models or paid delegation." >/dev/null

echo "Team started in workspace '$label'. Lead pane: $lead"
