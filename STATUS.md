Phase: Project closed on 1 November 2026, at the end of Phase 4 (digital design). It will not be built.
Done since last update: All design work is merged: the three boards (#126), the complete shopping list (#125), the last firmware items (#129) and the final design report, written in the style of an IB DT IA (docs/report/REPORT.md, #131). The owner reviewed the result and closed the project.
Owner's verdict: "Solid prototype." "Cost on receiver too high." "Needs new innovation at the highest level." The rack comes to £1,501.50 before VAT against the £800–830 hoped for, and the cost comes from the architecture (one receiver per pack, a large splitter board, wing antennas on stands), so cheaper parts cannot fix it (report section D6).
Costs (UK prices, never spent): the full shopping list came to £2,376.79 before VAT (£2,852.15 with VAT). Nothing was bought.
Next: none. A separate agent will audit the project. Start with docs/report/REPORT.md, then docs/design-log.md.
Waiting on human: nothing.
The risks below can no longer be closed, because they needed bench measurements:
Risks: (1) The dropout margin is thin (0.086 % against a 0.1 % worst-case limit), so the install rule must be followed: one antenna per wing, about 4 m up on a boom, aimed at the far upstage corner; no Wi-Fi in the wings or on stage; crew phones in airplane mode.
Risks: (2) The 2482 MHz carrier of pack 1 has not been simulated; it passes by equivalence, pending a measured occupied-bandwidth check.
Risks: (3) Bench calibration happens after the boards are designed, so a board re-spin is possible.
Risks: (4) Two pack amplifier settings (the antenna-select level and the amplifier mode pin) are unverified and can only be confirmed on the bench.
Risks: (5) Module certification paperwork is incomplete: the BT40NE whip is not on the FCC grant, and no UK or EU declaration has been published for the modules.
Risks: (6) The side rails of the rack case may touch the edge of the rack board; a test fit of the bare board settles it, and the edge can be notched if needed.
The full list of 18 open risks is in docs/design-log.md.
