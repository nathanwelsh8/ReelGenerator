"""Higgs model loader abstraction.

This module provides a lazy-loaded singleton interface to the (future) Higgs
TTS / voice synthesis model. For now it produces a simple sine tone placeholder
so the worker pipeline runs end-to-end. Replace the implementation inside
`_HiggsModel._infer_waveform` with real model logic (e.g., loading a HF model,
GPU tensors, etc.).
"""
from __future__ import annotations
import threading
import math
import wave
import struct
import os
import time
from typing import Dict, Any

from services.logger import logger
from settings import get_settings
from pathlib import Path

try:
    import torch  # type: ignore
except Exception:  # torch may not be available in non-GPU contexts
    torch = None  # type: ignore

_MODEL_SINGLETON = None
_MODEL_LOCK = threading.Lock()


class _HiggsModel:
    def __init__(self):
        settings = get_settings()
        self.model_id = settings.HIGGS_MODEL_ID  # unused for Boson flow (kept for backward compat)
        self.revision = settings.HIGGS_MODEL_REVISION  # unused for Boson flow
        self.device = settings.HIGGS_DEVICE
        self.use_half = settings.HIGGS_USE_HALF
        self.enable_gpu_metrics = settings.HIGGS_ENABLE_GPU_METRICS
        self.sample_rate = 16000
        self.voice_mode = settings.VOICE_MODE  # 'placeholder' | 'clone'
        self.provider = settings.HIGGS_MODEL_PROVIDER  # only 'boson' supported
        self.boson_model = settings.HIGGS_BOSON_MODEL
        self.boson_tokenizer = settings.HIGGS_BOSON_TOKENIZER
        self.ref_dir = settings.VOICE_REF_DIR
        self.embed_cache_dir = settings.VOICE_EMBED_CACHE
        os.makedirs(self.embed_cache_dir, exist_ok=True)
        self._speaker_cache: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Any] = {
            'load_start_time': time.time(),
            'load_duration_ms': None,
            'inference_count': 0,
            'total_inference_ms': 0.0,
        }
        self._gpu_props: Dict[str, Any] = {}
        self._load_model()

    def _load_model(self):
        start = time.time()
        if self.voice_mode == 'clone':
            if self.provider != 'boson':
                raise RuntimeError("Invalid HIGGS_MODEL_PROVIDER: only 'boson' (Higgs Audio v2) is supported.")
            # Use Boson Higgs Audio v2 API
            try:
                from boson_multimodal.serve.serve_engine import HiggsAudioServeEngine  # type: ignore
            except Exception as ie:
                logger.error("Failed to import Boson Higgs Audio package. Ensure it's installed in the runtime image.")
                raise
            device = 'cuda' if (torch is not None and torch.cuda.is_available() and self.device.startswith('cuda')) else 'cpu'
            self.model = HiggsAudioServeEngine(self.boson_model, self.boson_tokenizer, device=device)
            logger.info(f"Loaded Boson Higgs Audio ({self.boson_model}) on {device}")
        else:
            self.model = None
        if torch is not None and self.device.startswith('cuda') and torch.cuda.is_available():
            torch.cuda.empty_cache()
            if self.enable_gpu_metrics:
                try:
                    props = torch.cuda.get_device_properties(0)
                    self._gpu_props = {
                        'name': props.name,
                        'total_mem_mb': int(props.total_memory/1024/1024),
                    }
                except Exception as e:
                    logger.warning(f"Failed to get GPU properties: {e}")
        self._metrics['load_duration_ms'] = int((time.time() - start)*1000)
        logger.info(f"Higgs model loader initialized in {self._metrics['load_duration_ms']}ms (mode={self.voice_mode}, provider={self.provider})")

    def synthesize_to_wav(self, text: str, character: str, output_wav_path: str) -> Dict[str, Any]:
        """Generate audio for given text and character into a wav file.

        Returns a metrics dict for this inference.
        """
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
        start = time.time()
        meta: Dict[str, Any] = { 'voice_mode': self.voice_mode }
        if self.voice_mode == 'clone':
            try:
                wav, sr = self._clone_voice(text, character)
                # If model sample rate differs, resample later
                import soundfile as sf  # type: ignore
                sf.write(output_wav_path, wav, sr)
                meta['sample_rate'] = sr
            except Exception as e:
                # Fatal: do not fall back to placeholder when clone mode is requested.
                logger.error(f"Voice clone failed for character={character}: {e}")
                raise
        else:
            self._placeholder_generate(text, character, output_wav_path, meta)
        infer_ms = (time.time() - start) * 1000.0
        self._metrics['inference_count'] += 1
        self._metrics['total_inference_ms'] += infer_ms
        metrics = {
            'inference_ms': round(infer_ms, 2),
            'mean_inference_ms': round(self._metrics['total_inference_ms']/self._metrics['inference_count'], 2),
            **meta,
        }
        if torch is not None and self.enable_gpu_metrics and torch.cuda.is_available():
            try:
                mem_alloc = int(torch.cuda.memory_allocated()/1024/1024)
                mem_reserved = int(torch.cuda.memory_reserved()/1024/1024)
                metrics.update({
                    'gpu_mem_alloc_mb': mem_alloc,
                    'gpu_mem_reserved_mb': mem_reserved,
                })
            except Exception as e:
                logger.debug(f"GPU metric collection failed: {e}")
        return metrics

    # --- Internal helpers ---
    def _placeholder_generate(self, text: str, character: str, output_wav_path: str, meta: Dict[str, Any]):
        duration_sec = max(1.0, min(10.0, len(text) / 20.0))
        base_freq = 440.0
        if character:
            mod = (sum(ord(c) for c in character) % 200) - 100
            base_freq += mod
        self._infer_waveform(base_freq, duration_sec, output_wav_path)
        meta['mode_used'] = 'placeholder'

    def _clone_voice(self, text: str, character: str):
        if not character:
            raise ValueError("Character name required for clone mode")
        speaker = character.lower().replace(' ', '_')
        refs = self._gather_reference_files(speaker)
        if not refs:
            raise ValueError(f"No reference WAV files found for {speaker} under {self.ref_dir}")
        ref = self._select_best_reference(refs)

        if self.provider != 'boson':
            raise RuntimeError("Invalid provider: only 'boson' is supported for cloning")
        # Follow Higgs Audio v2 API: build ChatML messages with reference audio in conversation history
        try:
            from boson_multimodal.data_types import ChatMLSample, Message, AudioContent
            import base64
        except Exception as ie:
            raise RuntimeError(f"Boson higgs-audio not installed: {ie}")

        # Load and encode reference audio as base64
        with open(ref, 'rb') as f:
            ref_audio_bytes = f.read()
        ref_audio_base64 = base64.b64encode(ref_audio_bytes).decode('utf-8')
        
        # Create a placeholder transcript for the reference audio
        # Extract a simple phrase from filename or use generic text
        ref_filename = os.path.basename(ref)
        ref_text = ref_filename.replace('.wav', '').replace('.mp3', '').replace(' - AUDIO FROM JAYUZUMI.COM', '').strip()
        if not ref_text or len(ref_text) < 5:
            ref_text = f"This is {character} speaking."
        
        # Build message history with reference audio (voice cloning pattern from examples)
        messages = [
            Message(role="user", content=ref_text),
            Message(role="assistant", content=AudioContent(raw_audio=ref_audio_base64, audio_url="placeholder")),
            Message(role="user", content=text),
        ]
        
        # Higgs ServeEngine returns np audio and sampling_rate
        output = self.model.generate(
            chat_ml_sample=ChatMLSample(messages=messages),
            max_new_tokens=1024,
            temperature=0.3,
            top_p=0.95,
            top_k=50,
            stop_strings=["<|end_of_text|>", "<|eot_id|>"],
        )
        return output.audio, int(output.sampling_rate)

    def _gather_reference_files(self, speaker: str):
        base = Path(self.ref_dir) / speaker
        if not base.exists():
            return []
        # Support both .wav and .mp3 files as reference audio
        wav_files = [str(p) for p in base.glob('*.wav')]
        if wav_files:
            return wav_files
        # Fallback to mp3 if no wav files found
        mp3_files = [str(p) for p in base.glob('*.mp3')]
        return mp3_files

    def _select_best_reference(self, refs):
        # Heuristic: largest file (likely most speech content)
        return max(refs, key=lambda p: os.path.getsize(p))

    def _infer_waveform(self, freq: float, duration: float, path: str):
        frames = int(self.sample_rate * duration)
        with wave.open(path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            for i in range(frames):
                t = i / self.sample_rate
                sample = math.sin(2 * math.pi * freq * t)
                # Simple envelope fade in/out
                env = min(1.0, t * 5.0, (frames / self.sample_rate - t) * 5.0)
                sample *= env
                val = int(sample * 32767)
                wf.writeframes(struct.pack('<h', val))

def get_higgs_model() -> _HiggsModel:
    global _MODEL_SINGLETON
    if _MODEL_SINGLETON is not None:
        return _MODEL_SINGLETON
    with _MODEL_LOCK:
        if _MODEL_SINGLETON is None:
            _MODEL_SINGLETON = _HiggsModel()
    return _MODEL_SINGLETON
