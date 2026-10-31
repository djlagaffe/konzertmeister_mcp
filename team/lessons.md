# Verified repository lessons

- Packaging: Hatch needs `only-include = ["server.py"]` in its wheel target; default name discovery fails.
  Evidence: local pip install failed before this change, succeeded after; invalidate if modules move.
- Offline checks: `KM_API_KEY= .venv/bin/python -m unittest discover -s tests -v`.
  Five checks passed on Python 3.14 with mcp 1.30.0; CI also covers Python 3.11.
- Isolate HTTP with httpx.MockTransport; never test against the live Konzertmeister service.
- `.team-state/` is machine-local. TokenEconomizer `envfacts` and tool-pruning proposals use no auxiliary model.
