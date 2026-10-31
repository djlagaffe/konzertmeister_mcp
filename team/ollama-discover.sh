#!/usr/bin/env bash
# Read-only discovery: installed local weights only; never pulls or loads a model.
set -euo pipefail
command -v curl >/dev/null && command -v jq >/dev/null || { echo '{"url":null,"models":[]}'; exit 0; }
urls=(http://127.0.0.1:11434 http://10.0.2.2:11434)
[ -z "${OLLAMA_URL:-}" ] || urls=("$OLLAMA_URL")
for url in "${urls[@]}"; do
  url=${url%/}
  [[ "$url" =~ ^https?://[^[:space:]\"\']+$ ]] || continue
  if tags=$(curl -fsS --max-time 3 "$url/api/tags" 2>/dev/null) && \
    models=$(jq -ce '[.models[]? | select((.remote_host // "") == "" and (.remote_model // "") == "") | .name | select(type == "string" and test("^[A-Za-z0-9][A-Za-z0-9._:/-]*$") and (test("cloud"; "i") | not))] | unique' <<<"$tags" 2>/dev/null); then
    if [ "$(jq length <<<"$models")" -gt 0 ]; then
      jq -n --arg url "$url" --argjson models "$models" '{url:$url,models:$models}'
      exit 0
    fi
  fi
done
echo '{"url":null,"models":[]}'
