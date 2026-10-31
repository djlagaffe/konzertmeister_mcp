# Feature process (load for features, architecture changes or risky maintenance)

Roles: Lead coordinates; Challenger challenges; Architect designs; Builder implements; QA verifies;
Security Reviewer audits relevant risks; UI Reviewer exercises changed journeys; Documenter drafts prose;
Codex provides the independent model-family review. Load only the role needed for the task.

1. Challenge: read docs/00-brief.md. Record assumptions, risks, questions and scope in docs/01-challenge.md.
   Challenger and Codex review independently, subject to model approval. Gate A: PO approves scope.
2. Design: docs/02-design.md records structure, dependencies, threat model, checks and done criteria.
   Security Reviewer and Codex critique it. Gate B: PO approves design.
3. Build small increments from docs/03-plan.md. Write meaningful acceptance checks, implement, run
   team/check.sh and review the diff. The Lead may do routine work without creating a subagent.
4. Verify according to the review table in AGENTS.md. UI Reviewer runs changed user journeys and
   failure paths in the real app. Security review covers realistic threats in code/config only.
   Write evidence under docs/reviews/; link instead of duplicating it in summaries.
5. Before Gate C: full applicable checks, one security pass, independent Codex review and PO acceptance.
   Resolve blockers and verify fixes. Report remaining limits. Commit/push only within PO authorization.

Do not run every specialist after every increment. Named-file review for risky diffs; routine increments
need targeted checks and Lead diff review. Model approvals apply at every gate and delegation.
