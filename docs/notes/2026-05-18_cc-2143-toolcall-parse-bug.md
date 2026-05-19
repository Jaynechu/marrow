# Bug C — empty-turn-after-thinking (CC harness regression, introduced 2.1.142)

Status: OPEN — diagnosed 2026-05-18 via full-history jsonl differential scan, bucketed by CC version. Distinct from Bug A/B parse-fail.

## Symptom
Assistant emits a thinking block, then stop_reason=end_turn with NO text and NO tool_use. UI shows "thinking N s" then the turn ends and input returns — looks like a silent dropped reply. Thinking is complete and conclusive; the visible answer is never emitted.

## Root cause — CC harness regression at 2.1.142
Scan: 600 jsonl files, 8712 logical turns (aggregated by message.id; CC splits one turn's blocks across lines). True empty turns = 25.
- Bucketed by CC version: 2.1.116–2.1.141 ran thousands of opus-4-7 turns with ZERO empty turns. Empty turns appear ONLY at 2.1.142 (6) and 2.1.143 (19). First case 2026-05-15 = 2.1.142 start.
- opus-4-7 in use since 2026-04-21 — long before the bug. The earlier "24/24 opus-4-7" reading was collinearity (post-5-15 traffic is ~all opus-4-7), NOT model causation.
- Conclusion: harness regression, introduced exactly at 2.1.142. NOT a model-layer bug. Supersedes the model-layer hypothesis.
- No context correlation: output_tokens 293–5456, context as low as 34k.

## Mitigation
- Best: downgrade to 2.1.141 — newest version with zero empty-turn AND (Bug A #60033/#59787 is a 2.1.143 regression) zero parse-fail. Already installed locally. `claude install 2.1.141`, autoUpdates already false, restart CC.
- 2.1.133 also clean but unnecessarily old (8 versions back).
- Zero-cost in-session: reply any token ("继续" / "."), next turn recovers, context intact (verified 818a5fcc row28 empty → row35 normal).
- Re-pin 2.1.142 does NOT help — it is the version that introduced this bug (6 cases).
- Frequency ≈ 25/4996 ≈ 0.5% across 2.1.142+2.1.143; 0% on 2.1.141 and earlier.

## Re-run the scan
Aggregate jsonl type==assistant lines by message.id; true empty turn = aggregated block-type set == {thinking} AND stop_reason == end_turn. Glob ~/.claude/projects/*/*.jsonl. Bucket counts by `version` field.

## Followup
- Watch for a CC release past 2.1.143 that fixes both Bug A and Bug C; re-run the scan to confirm.