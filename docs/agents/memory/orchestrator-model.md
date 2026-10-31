---
name: orchestrator-model
description: OpenPack plan names Fable as orchestrator; user wants Opus 5.5 as master agent instead
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0a6bdcf3-3510-4946-9440-a93f854d0118
  modified: 2026-10-31T15:49:39.765Z
---

The OpenPack plan (wireless theater bodypack system) says Fable orchestrates; the user overrode that — run the master/orchestrator as Opus 5.5.

**Why:** user explicitly said "ignore that run the master agent as opus 5.5" (2026-10-31).
**How to apply:** don't spawn or defer to a Fable orchestrator; the main session (Opus) orchestrates. See [[openpack-audit]].
