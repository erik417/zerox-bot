"""
Fine-tune Nova (qwen2.5:3b) with LoRA on custom dataset.

Требования:
  - NVIDIA GPU (6GB+ для 3B модели)
  - pip install unsloth torch transformers datasets

Запуск:
  python finetune.py

После обучения:
  ollama create nova-finetuned -f Modelfile-finetuned
"""

import json
import torch
from datasets import Dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from transformers import TrainingArguments
from trl import SFTTrainer

# === Config ===
MODEL_NAME = "unsloth/qwen2.5-3b-instruct-bnb-4bit"
DATASET_PATH = "dataset.jsonl"
OUTPUT_DIR = "nova-lora"
MAX_SEQ_LENGTH = 2048

# === Load dataset ===
def load_jsonl(path):
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            data.append({
                "instruction": item["instruction"],
                "output": item["response"],
            })
    return data

# === Format as Alpaca ===
def format_alpaca(example):
    return {
        "text": (
            f"### Instruction:\n{example['instruction']}\n\n"
            f"### Response:\n{example['output']}"
        )
    }

# === Main ===
def main():
    print("Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        use_rslora=True,
    )

    raw_data = load_jsonl(DATASET_PATH)
    dataset = Dataset.from_list(raw_data).map(format_alpaca)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=3,
            learning_rate=2e-4,
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=1,
            output_dir=OUTPUT_DIR,
            save_strategy="epoch",
        ),
    )

    print("Training...")
    trainer.train()

    # Save LoRA weights
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Done! LoRA saved to {OUTPUT_DIR}")

    # Push to Ollama
    print("\nTo create Ollama model from LoRA, use:")
    print(f"  python convert_lora_to_ollama.py --lora {OUTPUT_DIR} --base qwen2.5:3b --name nova-finetuned")

if __name__ == "__main__":
    main()
