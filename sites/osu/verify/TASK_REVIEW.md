# OSU task review

All 20 tasks were re-grounded against the tracked seed source and the generated SQLite seed. Task URLs use OSU's current site index 20 and port `40020` after integration with current main.

| Task | Required visible workflow | Ground truth |
|---:|---|---|
| 0 | Academics | Fisher dean: Anil Makhija |
| 1 | About | Varsity Sports displayed: 36 |
| 2 | Athletics and two team details | Football and wrestling: Big Ten |
| 3 | Athletics to football | Ryan Day; 11-2 |
| 4 | Search to expenditure article | $1.3 billion; September 23, 2024 |
| 5 | About | 1870; Ohio Agricultural and Mechanical College |
| 6 | Research to TDAI | Beth Plale; four focus areas |
| 7 | About | 46,820; 14,000; difference 32,820 |
| 8 | Academics comparison | Engineering 8,000; Fisher 4,500; difference 3,500 |
| 9 | Engineering programs filter | BS, MS, PhD; three types |
| 10 | Athletics to wrestling | Tom Ryan; Covelli Center |
| 11 | Research to OSC | David Bickel; 1987 |
| 12 | Programs search to JD | JD; 90 credits; 3 years |
| 13 | Departments to Mathematics | James Cogdell; 100 Mathematics Building |
| 14 | Athletics and two team details | Football: Ohio Stadium; men's basketball: Value City Arena |
| 15 | Athletics comparison | Wrestling 8; fencing 2; difference 6 |
| 16 | MBA degree filter and detail | April 1; 60 credits; GRE not required |
| 17 | Search to cancer article | Exact title; Jody Sheridan |
| 18 | Research to James | William Farrar; four focus areas |
| 19 | Research to Clean Hydrogen | Yann Guezennec; 2022; four focus areas |

Read-only task verification compares every non-SQLite internal table before and after execution. Navigation checks parse URLs and require the same loopback origin, exact normalized paths, exact required query values, operation order, and visible-link click transitions where requested.
