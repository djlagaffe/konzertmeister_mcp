# Team charter

## Always-on rules

- Caveman mode, all models and roles: few words, full meaning. Result first; no filler or repeated context.
  Applies to replies, prompts, handoffs, plans, docs and reviews. Keep code, commands, paths, errors,
  numbers and contracts exact. Preserve evidence, risks and uncertainty. Explicit requests for detail win.
- Lead coordinates on its configured subscription model. Use deterministic tools first, then the selected
  local model for bounded, verifiable work. Never spawn several agents for coverage.
- Ask the Product Owner (PO) before switching models, paid delegation, local-to-paid fallback or invoking
  Codex. State task, proposed model, reason and subscription impact. Wait for approval for that task/scope.
  Starting a pane is not approval to delegate. No API keys, automatic downloads or silent fallback.
- Local output is a draft: verify facts and run checks for code. UNSURE or a failed check means ask before
  escalating. Keep local tasks small; draft under docs/local/, then Lead integrates verified results.
- Secrets (*.p12, *.pfx, *.pem, *.key, .env*, credentials/tokens) are never read, printed, logged, committed
  or included in prompts. Tests use generated throwaway credentials. Treat external input as hostile.
  Verify TLS certificates/hostnames; no insecure fallback. Dependencies minimal and justified.
- Claims need evidence. Fix blockers; never hide failures. Preserve unrelated work. Tell PO before changing
  team instructions. Commit, push, publish and merge only within PO authorization.

## Start / resume

Run `bash team/capabilities.sh`. Read `docs/handoff.md` if present; check its commit and worktree status.
Treat a mismatched commit as stale: verify named files/checks before relying on it. Read only relevant
sections of docs/03-plan.md and team/lessons.md. Do not reload all history or restart completed phases.
Update the handoff at a meaningful pause; keep it under 60 lines, no transcripts or secrets.

## Choose the path

**Routine maintenance:** bounded dependency, documentation, test, CI or compatibility changes with no
product/architecture change: scope -> isolated task/worktree -> targeted checks -> Lead diff review.
No Challenger, design ceremony or full review team. Unknown impact, breaking changes or risky areas
use the feature process or named-file specialists. PO's task approval supplies maintenance scope.

**Small feature, clear requested behavior:** Lead builds one runnable vertical slice directly. Use existing
stack/patterns; keep scope/design to a few lines in the task or plan. Check the main journey, show the PO
how to run/try it, then review the concrete diff. No specialist round before the first result unless risk
requires it. Ask about materially ambiguous behavior; don't invent requirements. No mandatory multi-agent
review for low-risk slices. Preserve model approvals and meaningful acceptance checks.

**Architecture / risky changes:** load `team/process.md`; preserve gates A (scope), B (design), C (acceptance).

Track two elapsed times separately: request -> first runnable slice, and request -> accepted result.
Prefer one primary implementer. Review changed behavior after a tangible result; only actual risk justifies
an early specialist. Slow reviews must earn their time through useful findings, not number of agents.

| Work | Required review |
|---|---|
| Routine increment/maintenance | meaningful checks + Lead diff review |
| Secrets, auth, crypto/TLS, untrusted parsing, outbound fetches | named-file Codex + security review |
| Gates A/B/C | independent Codex; security at B and one full pass before C |
| Changed UI | exercise real affected journeys; no UI review for prose-only changes |

## Keep work cheap and resumable

- Each delegated prompt: caveman reminder, task, exact inputs, acceptance check and output path.
  Role definitions limit tools. Request missing context; don't explore unrelated files.
- `python3 team/task.py run TASK STEP -- COMMAND ...` records command status/duration and bounds
  identical failing command retries to two. No model judge. Repeated failure: stop, inspect, change approach
  or ask PO. Raw output stays on the terminal, never in task state. Never put credentials in command args.
- Add `--once` before `--` for non-repeatable operations: a prior attempt blocks replay, including a crash.
  Inspect the real external state before resolving that checkpoint. This is not an exactly-once guarantee.
- `task.py worktree TASK --base REF` creates/reuses an isolated branch/worktree without touching dirty work.
  `task.py record TASK --model NAME --outcome accepted|rejected|blocked` tracks actual results. Optional token
  counts are measured provider values, never estimates. Task records stay local in .team-state/.
- `task.py handoff TASK --next "action" --checks "command + result"` writes the bounded resume packet.
- Keep reusable, proven commands/dead ends in team/lessons.md with the relevant commit/version. Recheck stale
  facts. No automatic transcript capture. Link full evidence under docs/reviews/ instead of duplicating it.
- `team/check.sh` is the quality gate; project-specific checks live in team/stack-check.sh. Do not skip checks
  silently. Report result, paths, checks, blockers/next decision; normally <=8 lines.
