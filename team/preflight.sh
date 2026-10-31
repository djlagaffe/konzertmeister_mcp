#!/usr/bin/env bash
# Verifies the team can run on subscriptions only (no API keys) and Herdr is wired up.
set -u
fail=0
bad() { echo "FAIL: $*" >&2; fail=1; }
ok()  { echo "ok:   $*"; }

for c in herdr claude codex jq curl; do
  command -v "$c" >/dev/null || bad "missing command: $c"
done

# API keys would silently switch billing away from the subscriptions.
for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN OPENAI_API_KEY CODEX_API_KEY; do
  [ -n "${!v:-}" ] && bad "$v is set; unset it so subscription auth is used"
done

if command -v claude >/dev/null; then
  if claude auth status 2>/dev/null | jq -e '.loggedIn == true and .authMethod == "claude.ai"' >/dev/null; then
    ok "claude: logged in via claude.ai subscription"
  else
    bad "claude is not logged in with a claude.ai subscription (run: claude auth login)"
  fi
fi

if [ -f "$HOME/.codex/auth.json" ]; then
  if jq -e '.auth_mode == "chatgpt"' "$HOME/.codex/auth.json" >/dev/null 2>&1; then
    ok "codex: logged in via ChatGPT subscription"
  else
    bad "codex is not using ChatGPT login (run: codex login)"
  fi
else
  bad "codex not logged in (run: codex login)"
fi

if command -v herdr >/dev/null; then
  for a in claude codex; do
    herdr integration status 2>/dev/null | grep -q "^$a: current" \
      && ok "herdr integration: $a" \
      || bad "herdr integration missing for $a (run: herdr integration install $a)"
  done
fi

exit $fail
