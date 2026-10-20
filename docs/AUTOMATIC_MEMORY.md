# Automatic memory capture — milestone 2

## What this adds
- A conservative rule-based extractor that only inspects user messages.
- Candidate queue: proposed memories remain pending and do not become durable memories until approved.
- Duplicate proposal suppression and candidate review history.
- CLI support to extract candidates from a JSON conversation export, list candidates, approve them, or reject them.

## Why approval is used first
Heuristics can misunderstand context, jokes, temporary wishes, hypotheticals, and sensitive information. The system should not silently turn every phrase into a permanent personal fact. This version proposes candidates for review; sensitive content still goes through the engine's sensitive-data guard.

## Use
Create a JSON file such as:

```json
[
  {"role": "user", "content": "Please remember that I prefer concise answers."},
  {"role": "assistant", "content": "Got it."}
]
```

Then run:

```bash
shivaay-memory extract --file conversation.json --project SHIVAAY --source-ref chat-001
shivaay-memory candidates
shivaay-memory approve-candidate --id 1
shivaay-memory reject-candidate --id 2
```

## Important limitation
This is not yet a language-model-powered extractor and does not automatically inspect a live chat stream. The next integration should call a model-backed structured extractor at the end of each conversation, then apply sensitivity, confidence, duplicate and conflict checks before approval or auto-save policies. Keep the extractor provider-neutral so a local model can be used on a low-resource Linux machine.
