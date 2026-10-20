# Structured model-backed extraction

SHIVAAY has a provider-neutral adapter in shivaay_memory.model_extraction.
It does not install an AI SDK, make network requests, or select a provider for you.
Pass a callable that receives a prompt and returns a JSON string (or decoded list).
This lets a local model runner be connected without changing the memory database.

Example:

    from shivaay_memory.model_extraction import StructuredModelExtractor

    def generate(prompt: str) -> str:
        return local_model.generate(prompt)

    extractor = StructuredModelExtractor(generate)
    candidates = extractor.extract(
        [{"role": "user", "content": "I'm building SHIVAAY as a local-first assistant."}],
        project="SHIVAAY",
    )
    # Send candidates to CandidateQueue(engine).propose(...); do not auto-approve.

## Safety and privacy

- Only user-role messages are included in the prompt; assistant replies are excluded as evidence of user facts.
- Model output is validated and bounded before it becomes a candidate.
- Durable storage still requires review through the existing candidate queue.
- This is a safety layer, not a guarantee against model hallucination. Check candidate text against its source.
- If the callable uses a cloud API, user message text leaves the machine. Local SQLite storage does not make cloud inference local. For strict local privacy, use a local inference backend.
