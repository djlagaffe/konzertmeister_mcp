#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
python_bin=${TEAM_PYTHON:-$root/.venv/bin/python}
[ -x "$python_bin" ] || python_bin=python3
KM_API_KEY= "$python_bin" -m unittest discover -s tests -v
"$python_bin" -m pip check
