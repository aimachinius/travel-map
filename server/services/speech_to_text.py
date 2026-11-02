"""
Module speech_to_text: Dịch vụ chuyển đổi giọng nói sang văn bản tiếng Việt sử dụng PhoWhisper-medium.
Tích hợp trích xuất âm thanh In-Memory (FFmpeg pipe), khử tạp âm noisereduce và lọc nhạc nền webrtcvad.
"""

import os
import subprocess
import time
from typing import Dict, Any, Optional
import numpy as np
import torch

import warnings
warnings.warn(
    "SpeechToTextEngine is deprecated as of AI Server v3.0 (Pure Vision architecture). "
    "Audio extraction and STT are no longer used.",
    DeprecationWarning,
    stacklevel=2,
)

from ...utils.logger import get_logger

logger = get_logger("SpeechToTextEngine")


def get_ffmpeg_binary() -> str:
    """Tự động tìm kiếm binary ffmpeg trong PATH hoặc các đường dẫn phổ biến."""
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    return "ffmpeg"


class SpeechToTextEngine:
    """
    Động cơ ASR nhận diện giọng nói tiếng Việt độ chính xác cao dựa trên vinai/PhoWhisper-medium.
    """
    def __init__(
        self,
        model_id: str = "vinai/PhoWhisper-medium",
        sample_rate: int = 16000,
        auto_load: bool = True,
    ):
        self.model_id = model_id
        self.sample_rate = sample_rate
        self.auto_load = auto_load
        self.use_cuda = torch.cuda.is_available()
        self.device = 0 if self.use_cuda else -1
        self.dtype = torch.float16 if self.use_cuda else torch.float32

        self.processor = None
        self.model = None
        self.asr_pipeline = None

        if self.auto_load:
            self.load_model()

    def load_model(self):
        """Khởi tạo và nạp mô hình PhoWhisper vào GPU/CPU."""
        if self.asr_pipeline is not None:
            return

        logger.info(f"Đang nạp mô hình PhoWhisper từ '{self.model_id}' (CUDA={self.use_cuda})...")
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
            use_safetensors=False,
        )
        if self.use_cuda:
            self.model.to("cuda")

        self.asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            chunk_length_s=30,
            device=self.device,
        )
        logger.info(f"Mô hình PhoWhisper-medium đã sẵn sàng hoạt động.")



    def _extract_audio_in_memory(self, video_path: str) -> np.ndarray:
        """
        Trích xuất âm thanh từ video trực tiếp vào RAM qua FFmpeg pipe.
        Không tạo bất kỳ file .wav tạm nào trên đĩa cứng.
        """
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [
            ffmpeg_bin, "-v", "error", "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", str(self.sample_rate),
            "-f", "s16le", "pipe:1"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode != 0 or len(res.stdout) == 0:
                return np.array([], dtype=np.float32)
            # Chuyển đổi byte PCM 16-bit signed integer thành float32 [-1.0, 1.0]
            return np.frombuffer(res.stdout, dtype="<i2").astype(np.float32) / 32768.0
        except Exception as e:
            logger.warning(f"Lỗi khi trích xuất âm thanh qua FFmpeg: {e}")
            return np.array([], dtype=np.float32)

    def _preprocess_audio(self, audio: np.ndarray) -> np.ndarray:
        """
        Khử tạp âm tĩnh môi trường (noisereduce) và lọc bỏ các đoạn nhạc nền / khoảng lặng (webrtcvad).
        """
        if audio.size == 0:
            return audio

        # 1. Khử tạp âm với mẫu 0.5s đầu
        clean_audio = audio
        try:
            import noisereduce as nr
            noise_sample = audio[: min(len(audio), int(self.sample_rate * 0.5))]
            clean_audio = nr.reduce_noise(
                y=audio,
                sr=self.sample_rate,
                y_noise=noise_sample,
                stationary=True,
                prop_decrease=0.8,
            )
        except Exception as e:
            logger.debug(f"Bỏ qua noisereduce do lỗi hoặc chưa cài đặt: {e}")

        # 2. WebRTC VAD lọc đoạn không có tiếng người (cửa sổ 30ms = 480 mẫu)
        try:
            import webrtcvad
            pcm = np.clip(clean_audio * 32767, -32768, 32767).astype(np.int16)
            vad = webrtcvad.Vad(2)  # Độ nhạy mức 2
            frame_size = int(self.sample_rate * 0.03)
            voiced_frames = []

            for start in range(0, len(pcm), frame_size):
                frame = pcm[start: start + frame_size]
                if len(frame) < frame_size:
                    frame = np.pad(frame, (0, frame_size - len(frame)))
                if vad.is_speech(frame.tobytes(), self.sample_rate):
                    voiced_frames.append(frame)

            if voiced_frames:
                clean_audio = np.concatenate(voiced_frames).astype(np.float32) / 32767.0
        except Exception as e:
            logger.debug(f"Bỏ qua WebRTC VAD: {e}")

        return clean_audio

    def transcribe_video(self, video_path: str) -> Dict[str, Any]:
        """
        Chuyển đổi toàn bộ âm thanh giọng nói trong video thành văn bản tiếng Việt.
        """
        if not os.path.exists(video_path):
            return {
                "text": "",
                "duration_seconds": 0.0,
                "status": "ERROR",
                "error_message": f"Không tìm thấy file: {video_path}",
            }

        start_t = time.time()
        # 1. Trích xuất âm thanh
        raw_audio = self._extract_audio_in_memory(video_path)
        if raw_audio.size == 0:
            return {
                "text": "",
                "duration_seconds": 0.0,
                "status": "NO_AUDIO",
                "error_message": "Không tìm thấy luồng âm thanh trong video",
            }

        duration_sec = round(len(raw_audio) / float(self.sample_rate), 2)

        # 2. Khử nhiễu & VAD
        clean_audio = self._preprocess_audio(raw_audio)

        # 3. Nạp model nếu chưa nạp
        if self.asr_pipeline is None:
            self.load_model()

        # 4. Suy luận ASR
        try:
            logger.info(f"Đang phiên âm video ({duration_sec}s audio) bằng PhoWhisper-medium...")
            result = self.asr_pipeline(
                {"raw": clean_audio, "sampling_rate": self.sample_rate},
                generate_kwargs={"task": "transcribe", "language": "vi"}
            )
            raw_text = str(result.get("text", "")).strip()
            clean_text = " ".join(raw_text.split())

            # Giải phóng VRAM đệm sau khi suy luận
            if self.use_cuda:
                torch.cuda.empty_cache()

            elapsed = round(time.time() - start_t, 2)
            logger.info(f"Phiên âm hoàn tất trong {elapsed}s: '{clean_text[:80]}...'")

            return {
                "text": clean_text,
                "duration_seconds": duration_sec,
                "status": "SUCCESS" if clean_text else "NO_SPEECH",
                "error_message": "",
            }
        except Exception as e:
            if self.use_cuda:
                torch.cuda.empty_cache()
            logger.error(f"Lỗi suy luận PhoWhisper: {e}")
            return {
                "text": "",
                "duration_seconds": duration_sec,
                "status": "ERROR",
                "error_message": str(e)[:200],
            }
