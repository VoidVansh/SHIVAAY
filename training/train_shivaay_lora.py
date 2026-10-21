#!/usr/bin/env python3
"""QLoRA supervised fine-tuning for SHIVAAY on a single CUDA GPU.

Expected JSONL format: one {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
conversation per line. Keep a held-out evaluation split; never evaluate on training examples.
"""
from __future__ import annotations

import os
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

MODEL_ID = os.environ.get("SHIVAAY_BASE_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
DATA_PATH = Path(os.environ.get("SHIVAAY_DATA", "data/shivaay_train.jsonl"))
OUTPUT_DIR = os.environ.get("SHIVAAY_OUTPUT", "outputs/shivaay-lora")
MAX_LENGTH = int(os.environ.get("SHIVAAY_MAX_LENGTH", "1024"))
SEED = int(os.environ.get("SHIVAAY_SEED", "42"))


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA GPU not found. Run this script in a GPU-enabled Kaggle/Colab session."
        )
    if not DATA_PATH.is_file():
        raise SystemExit(
            f"Training file not found: {DATA_PATH}\n"
            "Create a JSONL file with a 'messages' array per line; see training/README.md."
        )

    print(f"Base model: {MODEL_ID}")
    print(f"Dataset: {DATA_PATH}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"PyTorch: {torch.__version__}")

    raw = load_dataset("json", data_files=str(DATA_PATH), split="train")
    if len(raw) < 10:
        raise SystemExit(
            f"Only {len(raw)} examples found. Add at least 10 for a smoke test; "
            "a useful personality fine-tune generally needs a larger, diverse dataset."
        )
    if "messages" not in raw.column_names:
        raise SystemExit("Dataset must contain a 'messages' field with chat role/content objects.")

    split = raw.train_test_split(test_size=max(1, min(0.1, 1 / len(raw))), seed=SEED)
    train_data, eval_data = split["train"], split["test"]

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=quantization,
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=False,
    )
    model.config.use_cache = False

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )

    args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        learning_rate=1e-4,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        fp16=True,
        bf16=False,
        optim="paged_adamw_8bit",
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=25,
        save_strategy="steps",
        save_steps=25,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        max_length=MAX_LENGTH,
        packing=False,
        report_to="none",
        seed=SEED,
        dataset_num_proc=2,
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=train_data,
        eval_dataset=eval_data,
        processing_class=tokenizer,
        peft_config=lora,
    )
    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Adapter saved to: {OUTPUT_DIR}")
    print("Next: run held-out evaluations and compare against the unchanged base model.")


if __name__ == "__main__":
    main()
