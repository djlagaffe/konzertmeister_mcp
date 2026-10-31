#!/usr/bin/env bash
# Print which tiers are available right now. Never fails; the Lead records the result in docs/03-plan.md.
yn() { if "$@" >/dev/null 2>&1; then echo yes; else echo no; fi; }
has_agent() { command -v herdr >/dev/null && [ "${HERDR_ENV:-}" = 1 ] && herdr agent list 2>/dev/null | jq -e --arg name "$1" '.. | objects | select(.name? == $name)' >/dev/null; }
echo "local-pane: $(yn has_agent local)"
discovery=$(bash "$(dirname "$0")/ollama-discover.sh")
echo "ollama: $discovery"
echo "reviewer-pane(codex): $(yn has_agent reviewer)"
echo "claude: $(command -v claude >/dev/null && claude --version 2>/dev/null | head -1 || echo no)"
echo "codex: $(yn command -v codex)"
exit 0
