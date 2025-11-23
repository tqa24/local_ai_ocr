# src/worker.py
import io
import time
from PIL import Image
from PySide6.QtCore import QThread, Signal
from model_handler import ModelHandler
import file_handler

class OCRWorker(QThread):
    stream_chunk = Signal(str)
    image_started = Signal(str)
    image_finished = Signal(float)
    finished_all = Signal()
    error_occurred = Signal(str)

    def __init__(self, queue_items, prompt, model_path):
        super().__init__()
        self.queue_items = queue_items
        self.prompt = prompt
        self.model_path = model_path
        self.is_running = True

    def run(self):
        handler = ModelHandler.get_instance()

        # Load Model (May block on first run)
        try:
            handler.load_model(self.model_path)
        except Exception as e:
            self.error_occurred.emit(f"Model Load Failed: {e}")
            return

        # Process Queue
        for display_name, filepath, page_index in self.queue_items:
            if not self.is_running: break

            self.image_started.emit(f"\n--- Processing: {display_name} ---\n")
            start_time = time.time()

            try:
                # Read Data to RAM
                if page_index == -1:
                    img_bytes = file_handler.get_image_bytes(filepath)
                else:
                    img_bytes = file_handler.extract_pdf_page_bytes(filepath, page_index)

                # Convert to PIL Image (DeepSeek requires RGB)
                pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

                # Stream Inference
                full_text = ""
                for chunk in handler.stream_inference(pil_image, self.prompt):
                    if not self.is_running: break
                    self.stream_chunk.emit(chunk)
                    full_text += chunk

                # Clean up RAM
                pil_image.close()
                del img_bytes

                duration = time.time() - start_time
                self.image_finished.emit(duration)

            except Exception as e:
                self.error_occurred.emit(f"Error: {e}")

        self.finished_all.emit()

    def stop(self):
        self.is_running = False