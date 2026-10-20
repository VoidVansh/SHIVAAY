# Adaptive memory scoring and save policy

Each candidate receives transparent heuristic signals:
- **Durability:** whether it appears to describe a lasting preference, goal, decision, or rule; temporary language lowers this score.
- **Usefulness:** the candidate's importance and whether it belongs to a named project.
- **Confidence:** confidence supplied by the extractor.
- **Recurrence:** exact repeated mentions increment a counter and modestly increase the score; the boost is capped, and repetition is never proof of truth.
- **Sensitivity risk:** obvious sensitive markers trigger a hard exclusion from automatic saving.
- **Overall score:** weighted heuristic (40% durability, 35% usefulness, 25% confidence).

Candidate rows retain a recurrence count and last-seen timestamp. Existing databases are upgraded with additive SQLite column migrations; old candidates start with a count of one. Repeated mentions update the existing candidate instead of creating a second row. This initial version counts exact text matches within the same project only; paraphrases are not yet clustered.

Scores help prioritize review; they are not calibrated probabilities. They can be wrong. The candidate queue also includes an `auto_save_decision` and `auto_save_reason` for each item, explaining whether it is in review, blocked by a safeguard, already reviewed, or eligible under the current policy. Changing the policy does not retroactively approve old queued items. Sensitive-memory checks in the memory engine remain authoritative.

Automatic saving is **off by default**. Inspect the current policy:

```bash
shivaay-memory memory-policy
```

Opt in only if you want high-confidence, low-risk candidates saved without review:

```bash
shivaay-memory memory-policy --auto-save on --min-confidence 0.90 --min-score 0.85
```

Disable it at any time:

```bash
shivaay-memory memory-policy --auto-save off
```

Rule-based candidates currently have a confidence of 0.72, so the example policy will leave them in the review queue. Auto-save applies only when both configured thresholds are met, the sensitivity heuristic finds no risk, and no likely negation-based conflict with an active memory is detected in the same project. Likely conflicts stay pending for review rather than silently saving a contradictory claim. Conflict detection is a simple heuristic and may miss subtler contradictions or flag unusual wording. This is not a guarantee that a candidate is correct; keep the review-first default if reliability matters more than convenience.
