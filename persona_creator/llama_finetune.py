"""
Fine-tune Llama 3.2 3B on persona data using Unsloth
Output: Production-ready model with proper tokenizer format
use google colab and huggingface transformers, trl, and unsloth libraries.
remove hashes on line 8 and 191.
"""
# Step 0 — Install dependencies
#!pip install unsloth trl datasets accelerate transformers torch sentencepiece -q

print("✅ Dependencies installed")
import json
import torch
from pathlib import Path
from google.colab import files
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    MODEL_NAME = "unsloth/Llama-3.2-3B-Instruct-bnb-4bit"
    OUTPUT_DIR = "./steve_jobs_model"
    MAX_SEQ_LEN = 2048
    BATCH_SIZE = 2
    GRADIENT_ACCUMULATION = 4
    EPOCHS = 1
    LEARNING_RATE = 2e-4
    LORA_R = 16
    LORA_ALPHA = 16
    PERSONA_NAME = "Steve Jobs"


# ============================================================
# DATA LOADING & FORMATTING
# ============================================================

def load_jsonl(path: str) -> list:
    """Load JSONL file with validation"""
    if not Path(path).exists():
        raise FileNotFoundError(f"Training file not found: {path}")
    
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️ Skipping line {line_num}: {e}")
                continue
    return records


def format_record(record: dict, persona: str) -> str:
    """Format record into Llama 3.2 instruct format"""
    instruction = record.get("instruction", f"You are {persona}.")
    user_input = record.get("input", "")
    output = record.get("output", "")
    
    if not output:
        raise ValueError("Missing 'output' field in training record")
    
    if user_input:
        return (
            f"<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n{instruction}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n{output}<|eot_id|>"
        )
    else:
        return (
            f"<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n{instruction}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n{output}<|eot_id|>"
        )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    print("=" * 60)
    print("Fine-Tuning Pipeline — Steve Jobs Persona")
    print("=" * 60)
    
    # Step 1: Upload data
    print("\n📤 Upload finetune.jsonl file...")
    uploaded = files.upload()
    
    if not uploaded:
        raise RuntimeError("No file uploaded. Exiting.")
    
    file_path = list(uploaded.keys())[0]
    print(f"✅ Received: {file_path}")
    
    # Step 2: Load and validate data
    print("\n📂 Loading training data...")
    records = load_jsonl(file_path)
    print(f"   Loaded {len(records)} valid records")
    
    if len(records) < 10:
        print(f"⚠️ Warning: Only {len(records)} records. Minimum recommended: 50+")
    
    # Step 3: Load base model
    print(f"\n🤖 Loading base model: {Config.MODEL_NAME}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=Config.MODEL_NAME,
        max_seq_length=Config.MAX_SEQ_LEN,
        dtype=None,  # auto-detect
        load_in_4bit=True,
    )
    
    # Step 4: Add LoRA adapters
    print("🔧 Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=Config.LORA_R,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ],
        lora_alpha=Config.LORA_ALPHA,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    
    # Step 5: Prepare dataset
    print("📦 Preparing dataset...")
    formatted = [{"text": format_record(r, Config.PERSONA_NAME)} for r in records]
    dataset = Dataset.from_list(formatted)
    
    print(f"   Sample:\n{formatted[0]['text'][:200]}...")
    
    # Step 6: Configure trainer
    print("\n🚀 Initializing trainer...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=Config.MAX_SEQ_LEN,
        args=TrainingArguments(
            output_dir=Config.OUTPUT_DIR,
            per_device_train_batch_size=Config.BATCH_SIZE,
            gradient_accumulation_steps=Config.GRADIENT_ACCUMULATION,
            num_train_epochs=Config.EPOCHS,
            learning_rate=Config.LEARNING_RATE,
            fp16=True,
            logging_steps=10,
            save_steps=100,
            warmup_steps=10,
            report_to="none",  # Disable wandb
        ),
    )
    
    # Step 7: Train
    print("\n🔥 Starting training...")
    print(f"   Epochs: {Config.EPOCHS}")
    print(f"   Batch size: {Config.BATCH_SIZE}")
    print(f"   Effective batch: {Config.BATCH_SIZE * Config.GRADIENT_ACCUMULATION}")
    trainer.train()
    
    # Step 8: Save with fast tokenizer
    print(f"\n💾 Saving model to {Config.OUTPUT_DIR}")
    
    # Save with fast tokenizer (for production)
    tokenizer.save_pretrained(Config.OUTPUT_DIR, legacy_format=False)
    model.save_pretrained(Config.OUTPUT_DIR)
    
    # Also save merged 16-bit version for deployment
    merged_dir = f"{Config.OUTPUT_DIR}_merged"
    print(f"💾 Saving merged model to {merged_dir}")
    model.save_pretrained_merged(
        merged_dir,
        tokenizer,
        save_method="merged_16bit",
    )
    
    # Step 9: Package for download
    print("\n📦 Packaging model...")
    #!zip -r steve_jobs_model.zip {Config.OUTPUT_DIR} {merged_dir}
    
    # Step 10: Download
    print("⬇️ Downloading model...")
    files.download("steve_jobs_model.zip")
    
    print("\n✅ Complete!")
    print(f"   Model size: ~2.5GB")
    print(f"   Recommended for: 8GB+ VRAM")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()