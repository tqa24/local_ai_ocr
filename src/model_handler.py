# src/model_handler.py
import sys
import os
import torch
import threading
import math
import gc
from PIL import Image, ImageOps
from transformers import AutoModel, AutoTokenizer, TextIteratorStreamer, LogitsProcessor, LogitsProcessorList

# Custom Logits Processor to prevent infinite looping
class DeepSeekNGramLogitsProcessor(LogitsProcessor):
    def __init__(self, ngram_size, window_size, whitelist_token_ids):
        self.ngram_size = ngram_size
        self.window_size = window_size
        self.whitelist_token_ids = set(whitelist_token_ids)

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        # input_ids: [batch, seq_len]
        # Iterate over the batch
        for batch_idx in range(input_ids.shape[0]):
            seq = input_ids[batch_idx].tolist()

            # We need enough tokens to form an n-gram
            if len(seq) < self.ngram_size:
                continue

            # The prefix we are trying to extend (the last n-1 tokens)
            prefix_len = self.ngram_size - 1
            current_prefix = seq[-prefix_len:]

            # Define the search window (last 'window_size' tokens)
            # We only care if the prefix appeared recently, causing a local loop.
            # If window_size is None, search the whole sequence.
            search_start = max(0, len(seq) - self.window_size) if self.window_size else 0

            # We assume the repetition occurs *within* the window.
            # We look at the history slice excluding the current incomplete prefix at the very end.
            history_slice = seq[search_start : -prefix_len]

            # Iterate through history to find occurrences of the current_prefix
            # If found, the token immediately following it is a candidate for banning.
            # This is a simple O(N*M) search, but given M=29 and N=90, it's very fast.
            for i in range(len(history_slice) - prefix_len + 1):
                # check match
                if history_slice[i : i + prefix_len] == current_prefix:
                    # Found a match. The next token in history is what we want to ban
                    # to prevent repeating the same sequence.
                    banned_token = history_slice[i + prefix_len]
                    
                    if banned_token not in self.whitelist_token_ids:
                        scores[batch_idx, banned_token] = -float('inf')

        return scores

class ModelHandler:
    _instance = None
    _model = None
    _tokenizer = None
    _device = None
    _model_module = None 

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # Detects GPU. Falls back to CPU if GPU is missing, broken, or ancient.
    def _get_optimal_device(self):
        # Check for forced CPU override
        if os.environ.get("FORCE_CPU", "0") == "1":
            print("Device: CPU (Forced by User)")
            return "cpu", torch.float32

        # Check generic availability
        if not torch.cuda.is_available():
            print("Device: CPU (No GPU detected)")
            return "cpu", torch.float32

        # Test for Ancient/Broken GPUs
        try:
            # Try to allocate a tiny tensor on VRAM
            t = torch.tensor([1.0]).cuda()
            _ = t * 2
            del t
            # If successful, use GPU
            print(f"Device: GPU ({torch.cuda.get_device_name(0)})")
            return "cuda", torch.bfloat16
        except Exception as e:
            print(f"Device: CPU (GPU detected but unusable: {e})")
            return "cpu", torch.float32

    def load_model(self, model_path):
        if self._model is not None: 
            return

        self._device, dtype = self._get_optimal_device()
        print(f"Loading model on {self._device} ({dtype}), this may take a while...")

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            
            # 'attn_implementation="eager"' is critical for Windows/CPU compatibility
            # It avoids the requirement for compiling flash_attn kernels
            self._model = AutoModel.from_pretrained(
                model_path, 
                trust_remote_code=True, 
                attn_implementation="eager", 
                dtype=dtype
            ).to(self._device).eval()
            
            # Dynamically grab the module to access 'dynamic_preprocess' logic
            # This borrows code from modeling_deepseekocr.py
            self._model_module = sys.modules[self._model.__module__]
            print("Model loaded successfully.")

        except Exception as e:
            # Final safety check: If loading on GPU fails unexpectedly (Out of VRAM, ...), try CPU
            if self._device == "cuda":
                print(f"GPU Load Failed ({e}). Retrying on CPU...")
                self._device = "cpu"
                self._model = AutoModel.from_pretrained(
                    model_path, trust_remote_code=True, attn_implementation="eager", dtype=torch.float32
                ).to("cpu").eval()
                self._model_module = sys.modules[self._model.__module__]
            else:
                raise e

    def unload_model(self):
        # Manually unloads the model to free RAM/VRAM.
        if self._model is not None:
            print("Unloading model...")
            del self._model
            del self._tokenizer
            del self._model_module
            self._model = None
            self._tokenizer = None
            self._model_module = None
            
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("Model unloaded.")

    def stream_inference(self, pil_image, prompt, base_size=1024):
        # Custom implementation of 'infer' that supports Streaming and In-Memory Images.
        # Replicates logic from modeling_deepseekocr.py without tempfiles.
        if not self._model:
            raise RuntimeError("Model not loaded.")

        # Borrow helper functions from the loaded model code
        dynamic_preprocess = self._model_module.dynamic_preprocess
        BasicImageTransform = self._model_module.BasicImageTransform
        text_encode = self._model_module.text_encode

        # --- CONSTANTS (DeepSeek Architecture) ---
        # These must match the model's internal settings
        PATCH_SIZE = 16
        DOWNSAMPLE_RATIO = 4
        BLOCK_SIZE = PATCH_SIZE * DOWNSAMPLE_RATIO # 64 pixels per token block

        # 100 features -> 10x10 grid -> 640px crops
        CROP_SIZE = 640 

        # --- PREPROCESSING ---
        image_transform = BasicImageTransform(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5), normalize=True)

        # Logic: Gundam Mode (Dynamic Tiling)
        # Only tile if the image is larger than the patch window (640)
        crop_mode = True if (pil_image.size[0] > CROP_SIZE or pil_image.size[1] > CROP_SIZE) else False

        images_list, images_crop_list, images_spatial_crop = [], [], []

        # Global View (Base)
        global_view = ImageOps.pad(pil_image, (base_size, base_size), color=(128, 128, 128))
        images_list.append(image_transform(global_view).to(self._model.dtype))

        if crop_mode:
            # Note: dynamic_preprocess usually defaults to image_size=640 internally
            images_crop_raw, crop_ratio = dynamic_preprocess(pil_image)
            images_spatial_crop.append(crop_ratio)
            for crop in images_crop_raw:
                images_crop_list.append(image_transform(crop).to(self._model.dtype))
        else:
            images_spatial_crop.append([1, 1])

        # --- TENSOR PREPARATION ---
        images_ori = torch.stack(images_list, dim=0).to(self._device)

        if images_crop_list:
            images_crop = torch.stack(images_crop_list, dim=0).to(self._device)
        else:
            # Dummy for small images
            images_crop = torch.zeros((1, 3, CROP_SIZE, CROP_SIZE)).to(self._device).to(self._model.dtype)

        # --- TOKEN CONSTRUCTION ---
        image_token_id = 128815 

        # Calculate Grid Sizes correctly using PIXEL dimensions
        base_grid_side = base_size // BLOCK_SIZE  # 1024 // 64 = 16
        crop_grid_side = CROP_SIZE // BLOCK_SIZE  # 640 // 64 = 10

        width_crop_num, height_crop_num = images_spatial_crop[0]

        # Build Base Tokens: ([tok]*16 + [tok]) * 16 + [tok]
        tokenized_image = ([image_token_id] * base_grid_side + [image_token_id]) * base_grid_side
        tokenized_image += [image_token_id]

        # Build Crop Tokens: ([tok]*Width + [tok]) * Height
        if len(images_crop_list) > 0:
            total_width = crop_grid_side * width_crop_num
            total_height = crop_grid_side * height_crop_num
            tokenized_image += ([image_token_id] * total_width + [image_token_id]) * total_height

        # --- FINAL ASSEMBLY ---
        full_prompt = f"<|User|>{prompt}\n<|Assistant|>"
        tokenized_prompt = text_encode(self._tokenizer, full_prompt, bos=False, eos=False)

        final_input_ids = [0] + tokenized_image + tokenized_prompt # 0 is BOS

        # Mask: False for BOS, True for Image, False for Prompt
        images_seq_mask = [False] + [True] * len(tokenized_image) + [False] * len(tokenized_prompt)

        # Convert to Tensors
        input_ids = torch.LongTensor(final_input_ids).unsqueeze(0).to(self._device)
        # DeepSeek expects BoolTensor for this mask
        images_seq_mask = torch.tensor(images_seq_mask, dtype=torch.bool).unsqueeze(0).to(self._device)
        images_spatial_crop = torch.tensor(images_spatial_crop, dtype=torch.long).to(self._device)

        # --- PROCESSORS (LOOP PREVENTION) ---
        # Logic from vLLM example to prevent infinite loops
        loop_processor = DeepSeekNGramLogitsProcessor(
            ngram_size=30, 
            window_size=90, 
            whitelist_token_ids={128821, 128822} # <td>, </td>
        )

        streamer = TextIteratorStreamer(self._tokenizer, skip_prompt=True, skip_special_tokens=True)

        gen_kwargs = dict(
            input_ids=input_ids,
            images=[(images_crop, images_ori)], 
            images_seq_mask=images_seq_mask,
            images_spatial_crop=images_spatial_crop,
            streamer=streamer,
            max_new_tokens=4096,
            do_sample=False,
            use_cache=True,
            eos_token_id=self._tokenizer.eos_token_id,
            logits_processor=LogitsProcessorList([loop_processor]) # Add our processor
        )

        thread = threading.Thread(target=self._model.generate, kwargs=gen_kwargs)
        thread.start()

        for new_text in streamer:
            yield new_text

        thread.join()