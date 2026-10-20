# Adaptive memory scoring and save policy

Each candidate receives transparent heuristic signals:
- **Durability:** whether it appears to describe a lasting preference, goal, decision, or rule; temporary language lowers this score.
- **Usefulness:** the candidate's importance and whether it belongs to a named project.
- **Confidence:** confidence supplied by the extractor.
- **Sensitivity risk:** obvious sensitive markers trigger a hard exclusion from automatic saving.
- **Overall score:** weighted heuristic (40% durability, 35% usefulness, 25% confidence).

Scores help prioritize review; they are not calibrated probabilities. They can be wrong. Sensitive-memory checks in the memory engine remain authoritative.

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

Rule-based candidates currently have a confidence of 0.72, so the example policy will leave them in the review queue. Auto-save applies only when both configured thresholds are met and the sensitivity heuristic finds no risk. This is not a guarantee that a candidate is correct; keep the review-first default if reliability matters more than convenience.
