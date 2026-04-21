#!/usr/bin/env python3
"""Fine-tune distilbert for Pass-2 binary classifier (PRD §8.1).

Usage:
  pip install torch transformers datasets accelerate
  python scripts/train_distilbert_classifier.py --data evals/extractor_v1.jsonl --out models/problem_classifier

Then set SIGNAL_CLASSIFIER_MODEL_PATH=models/problem_classifier
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import Dataset


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("evals/extractor_v1.jsonl"))
    p.add_argument("--out", type=Path, default=Path("models/problem_classifier"))
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--model", default="distilbert-base-uncased")
    args = p.parse_args()

    rows: list[dict] = []
    with args.data.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            rows.append({"text": o["text"], "label": 1 if o.get("is_problem_signal") else 0})

    ds = Dataset.from_list(rows).train_test_split(test_size=0.15, seed=42)

    from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    def tok_map(examples: dict) -> dict:
        enc = tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=256,
        )
        enc["labels"] = examples["label"]
        return enc

    train_raw = ds["train"].map(tok_map, batched=True, remove_columns=ds["train"].column_names)
    eval_raw = ds["test"].map(tok_map, batched=True, remove_columns=ds["test"].column_names)
    cols = ["input_ids", "attention_mask", "labels"]
    train_raw.set_format("torch", columns=cols)
    eval_raw.set_format("torch", columns=cols)

    args.out.mkdir(parents=True, exist_ok=True)
    targs = TrainingArguments(
        output_dir=str(args.out),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_steps=20,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_raw,
        eval_dataset=eval_raw,
    )
    trainer.train()
    trainer.save_model(str(args.out))
    tokenizer.save_pretrained(str(args.out))
    print(f"Saved classifier to {args.out}")


if __name__ == "__main__":
    main()
