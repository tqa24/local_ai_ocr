# ./get_model.py
import os
from huggingface_hub import snapshot_download

# ./models/DeepSeek-OCR/
MODEL_DIR = os.path.join("models", "DeepSeek-OCR")

def main():
    print(f"Setting up model in: {MODEL_DIR}")

    # Download code files from th1nhhdk/DeepSeek-OCR-LatestTransformers-CPU
    # This fork is patched for CPU/MPS and transformers version 4.57+ compatibility
    print("--- Downloading th1nhhdk/DeepSeek-OCR-LatestTransformers-CPU... ---")
    snapshot_download(
        repo_id="th1nhhdk/DeepSeek-OCR-LatestTransformers-CPU",
        revision="596a21a55c486ff9dfe27a4f7653effd3e8531b0",
        local_dir=MODEL_DIR
    )

    print("\nModel setup complete.")
    print("You can now run 'run.bat' or 'run_cpu-only.bat'")

if __name__ == "__main__":
    main()