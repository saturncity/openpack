---
name: prefer-3d-printed
description: "Owner prefers 3D-printed parts over bought mechanical parts (clips, panels, brackets)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 88d66881-5728-4898-b403-06a613ad587f
  modified: 2026-10-31T20:22:55.385Z
---

Default mechanical parts to 3D-printed (PETG) rather than bought, e.g. belt clip and 1U rack panel (printed in bed-sized segments).

**Why:** Owner said "id rather more be made 3d printed" when I proposed a bought spring-steel clip and aluminium panel (2026-10-31, #35, ADR-0008).

Owner's printer: Bambu Lab A1 mini, 180 × 180 × 180 mm, open frame; PETG OK (textured plate), avoid ABS/ASA.

**How to apply:** For enclosure/mech decisions, design a printable version first (split to fit the 180 mm bed); only buy when printing can't meet a requirement, and say why. Owner is hands-off otherwise, see [[hands-off-owner]].
