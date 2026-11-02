"""
Module test_speech_to_text: Kiểm thử độc lập Module 2 - SpeechToTextEngine (PhoWhisper-medium).
"""

import os
import unittest
import numpy as np

from src.server.services.speech_to_text import SpeechToTextEngine
from src.config.settings import get_default_videos_dir


@unittest.skip("Deprecated in Server v3.0 Pure Vision specification (Speech-to-Text removed)")
class TestSpeechToTextEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Khởi tạo engine ở chế độ lazy load để không nạp model nặng nếu chỉ test logic audio
        cls.engine = SpeechToTextEngine(model_id="vinai/PhoWhisper-medium", auto_load=False)

    def test_transcribe_non_existent_file(self):
        res = self.engine.transcribe_video("path/to/non_existent_video.mp4")
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["text"], "")

    def test_audio_preprocessing_pipeline(self):
        # Tạo mảng âm thanh giả lập (16kHz, 1 giây)
        sample_rate = 16000
        t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
        # Sóng sin 440Hz (tiếng còi giả lập) + tạp âm trắng
        tone = 0.5 * np.sin(2 * np.pi * 440 * t)
        noise = 0.05 * np.random.randn(sample_rate).astype(np.float32)
        dummy_audio = np.clip(tone + noise, -1.0, 1.0)

        # Chạy qua bộ khử nhiễu và lọc VAD
        clean_audio = self.engine._preprocess_audio(dummy_audio)
        self.assertIsInstance(clean_audio, np.ndarray)
        self.assertGreater(clean_audio.size, 0)

    def test_transcribe_local_sample_if_available(self):
        import shutil
        from src.server.services.speech_to_text import get_ffmpeg_binary
        ffmpeg_bin = get_ffmpeg_binary()
        if not shutil.which(ffmpeg_bin) and not (os.path.isabs(ffmpeg_bin) and os.path.exists(ffmpeg_bin)):
            self.skipTest("FFmpeg binary không có sẵn trong môi trường test này (sẽ chạy đầy đủ trên Colab/Linux).")

        videos_dir = get_default_videos_dir()
        sample_video = None
        if os.path.exists(videos_dir):
            for f in os.listdir(videos_dir):
                if f.endswith(".mp4"):
                    sample_video = os.path.join(videos_dir, f)
                    break

        if sample_video and os.path.exists(sample_video):
            raw_audio = self.engine._extract_audio_in_memory(sample_video)
            self.assertIsInstance(raw_audio, np.ndarray)
            self.assertGreater(raw_audio.size, 0)
            duration_sec = len(raw_audio) / float(self.engine.sample_rate)
            self.assertGreater(duration_sec, 0.5)


if __name__ == "__main__":
    unittest.main()
