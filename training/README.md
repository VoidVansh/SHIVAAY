# SHIVAAY model fine-tuning (cloud-first)

This is the first reproducible path for adapting an existing model into SHIVAAY. It does **not** pretrain a foundation model from scratch.

## Candidate and hardware

Initial practical candidate: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0; approximately 8.1 GB of BF16/FP16 weights before quantization). It is small enough for 4-bit LoRA fine-tuning on a Kaggle T4-class GPU, subject to the notebook's available VRAM and package versions. We should still benchmark it against a suitable base checkpoint before declaring it the final model, because an instruct checkpoint already carries a pre-existing assistant style.

## Data format

Put the approved examples in `data/shivaay_train.jsonl`, one JSON object per line, using either:

```json
{"messages":[{"role":"user","content":"How should you respond when you are uncertain?"},{"role":"assistant","content":"I'll say what I know, separate facts from guesses, and explain what I'd need to verify."}]}
```

Use only examples you have permission to use. Keep private or sensitive real conversations out unless deliberately reviewed and approved. Do not put tokens, passwords, private keys, or raw personal memory databases in the training set.

## Run on Kaggle

1. Enable a GPU accelerator and Internet access.
2. Upload this repository or clone it into the notebook.
3. Install the dependencies listed in `requirements-training.txt`.
4. Upload/copy the JSONL dataset to `data/shivaay_train.jsonl`.
5. Run `python training/train_shivaay_lora.py`.
6. Inspect the sample generations and training logs before using the adapter.
7. Keep the base model and adapter separate; do not overwrite the base model.

The script saves an adapter to `outputs/shivaay-lora`. Training is not run automatically by committing these files; a GPU notebook must execute them.

## What this first pass does and doesn't do

- Uses supervised fine-tuning with LoRA adapters; it does not erase the base model's knowledge or guarantee removal of its inherited behavior.
- Focuses on SHIVAAY's identity, communication style, honesty, disagreement behavior, and response habits.
- Does not implement memory. SHIVAAY's SQLite memory system remains a separate retrieval layer.
- Does not run RLHF/DPO yet. First validate the dataset and baseline; then add preference optimization only if comparisons show a clear need.
- Does not promise an “uncensored” result. Fine-tuning can change response tendencies but cannot guarantee the removal of all refusals or inherited biases.

## Evaluation gate

Before and after fine-tuning, test the same held-out prompts for: identity consistency, natural Hinglish, truthfulness under uncertainty, useful disagreement, instruction following, memory-boundary honesty, refusal behavior, and regression in general reasoning. Do not train on the held-out evaluation prompts.
