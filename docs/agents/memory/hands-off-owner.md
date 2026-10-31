---
name: hands-off-owner
description: OpenPack owner is non-technical and has pre-approved all in-scope work; never block on engineering questions
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79182c87-020e-4b9a-bd8d-61c3be8c6ce4
  modified: 2026-10-31T16:28:37.378Z
---

The user has no electronics, RF, audio, or firmware background and wants hands-off development: agents decide everything within the scope of PLAN.md, and only ask for purchases, physical steps (plugging in boards), out-of-scope changes, safety/legal, or an unachievable requirement. Decisions outside the QUESTIONS.md defaults are scored against the ranked REQUIREMENTS.md in an ADR.

**Why:** "i dont know anything about any of this so id rather just approve all handsoff within the scope of this project."

**How to apply:** Don't ask the user to judge codecs, chips, topologies, or layouts. Write zero-knowledge checklists (docs/human/) for any physical step. Keep STATUS.md readable by a non-engineer. Rules live in docs/agents/hands-off.md. See [[orchestrator-model]].
