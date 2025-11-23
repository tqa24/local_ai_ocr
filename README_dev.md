# Local AI OCR (v2.0)

## Tech Stack
- **Python:** Embeddable Python (3.12.9)
- **Engine:** PyTorch (2.6.0)
- **Model weights:** deepseek-ai/DeepSeek-OCR (9f30c71f441d010e5429c532364a86705536c53a)
- **Model code:** Dogacel/DeepSeek-OCR-Metal-MPS (6b272b4d892d5de56470330f072ce7415b79be49)
- **Frontend:** PySide6 (Qt6)

## Environment setup

### Automated
- Execute `env_setup.bat`.

### Manual
1. **Python:**
   - Download [Python 3.12.9 Embeddable (Windows x64)](https://www.python.org/ftp/python/3.12.9/python-3.12.9-embed-amd64.zip).
   - Extract to `python/`.
   - Edit `python/python312._pth`: Uncomment line 5: `import site`.

2. **pip + requirements:**
   - Download [get-pip.py](https://bootstrap.pypa.io/get-pip.py).
     ```powershell
     .\python\python.exe get-pip.py
     .\python\python.exe -m pip install -r requirements.txt
     ```

3. **DeepSeek-OCR Model:**
    ```powershell
    .\python\python.exe get_model.py
    ```

## Running
- **With GPU (If possible):** `run.bat`
- **CPU-Only Mode:** `run_cpu-only.bat`

## Troubleshooting
- `"CUDA error: no kernel image is available":` Your GPU is too old. Use `run_cpu-only.bat`.