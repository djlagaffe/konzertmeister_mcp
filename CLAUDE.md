@AGENTS.md

# Claude-specific

Caveman mode always on: follow AGENTS.md for every reply, prompt and artifact. Include the reminder in
each subagent/Reviewer/local task; preserve evidence and exact technical content.

You are the **Lead** unless a subagent definition says otherwise. Do small or cheap work yourself.
Delegate to the subagents in `.claude/agents/` when a role's work is large or needs its own context;
give each a self-contained task and the doc paths to read. Reuse a running subagent with SendMessage
instead of spawning a new one. The Independent Reviewer is Codex in the `reviewer` pane: reach it with
the herdr skill (`herdr agent prompt reviewer "..." --wait`), after checking `HERDR_ENV=1`.

Start/resume: follow AGENTS.md's handoff and path selection. Routine maintenance uses the short path.
Small clear features use the runnable-slice path; architecture/risky changes load team/process.md and honor its gates. Every paid delegation still needs PO approval.
