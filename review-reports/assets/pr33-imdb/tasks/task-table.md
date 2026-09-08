# Recorded task excerpts

These are the ten retained task executions. The runner was isolated from implementation, answer keys and scoring outputs, but retained its own preceding UI context, including the retired tasks. This is not a fresh-context model success-rate study. Each final JPEG is copied byte-for-byte from the original capture and hash-checked; a final image is an excerpt, not evidence of the entire run.

All ten retained executions pass the native deterministic evaluator at commit `a37df75a873842be0ed4510baab5dbff361ac9ad`. Claude review is **NOT_EXECUTED**. Full original evidence is retained privately.

| Task | Executed version | Recorded steps | Successful substantive actions | Recorded issue | Final JPEG |
|---|---|---:|---:|---|---|
| IMDb--0 | r2 | 5 | 4 | None recorded | [Image](IMDb--0-final.jpg) |
| IMDb--2 | r2 | 6 | 4 | bookkeeping | [Image](IMDb--2-final.jpg) |
| IMDb--7 | r2 | 5 | 3 | None recorded | [Image](IMDb--7-final.jpg) |
| IMDb--9 | r2 | 10 | 6 | ui_action | [Image](IMDb--9-final.jpg) |
| IMDb--10 | r2 | 15 | 14 | None recorded | [Image](IMDb--10-final.jpg) |
| IMDb--12 | r2 | 11 | 9 | None recorded | [Image](IMDb--12-final.jpg) |
| IMDb--14 | r2 | 7 | 6 | None recorded | [Image](IMDb--14-final.jpg) |
| IMDb--15 | r2 | 14 | 12 | None recorded | [Image](IMDb--15-final.jpg) |
| IMDb--16 | r2 | 11 | 10 | None recorded | [Image](IMDb--16-final.jpg) |
| IMDb--17 | r1 | 14 | 12 | None recorded | [Image](IMDb--17-final.jpg) |

Counts exclude observations, scrolling, failed actions and preparation/bookkeeping. Login form fills count as successful actions; no credential values are included.

Task17 retains r1: base `ebe92f…` plus frozen working-input hashes, image `ee00ec…`, HF `4d5709…`. The other nine use r2: code `50bcce…`, image `74aec2…`, HF `e70f49…`. Full identifiers, original hashes, recorded final answers and prior UI context are in [task-results.json](task-results.json).

Seven observed paths used at least five successful substantive actions (9/10/12/14/15/16/17). Tasks0/12/14 compare information. The observed paths do not prove a minimum over every legal route. Task10’s tied leaders and tasks15/16’s personal initial-state constraints support the design judgment that precision can challenge a frontier model; empirical difficulty remains **NOT_VERIFIED**.

Tasks3/4/8 were removed after quality review: the first two resolve on the first matching title detail; task8 has a stable common-knowledge shortcut. The original thirteen runs and old scoring outputs remain unchanged.

Recorded issues in this retained set: task2’s duplicate manifest attempt was rejected before a corrected helper call; task9 recorded one failed Type selector action and recovered using the observed control. See the structured records for those disclosures.
