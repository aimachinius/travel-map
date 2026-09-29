import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from stt3 import SpeechToTextModel


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.original = np.zeros(32000, dtype=np.float32)
        self.compressed = np.ones(16000, dtype=np.float32)
        self.backend = SimpleNamespace(
            build_phowhisper_pipeline=Mock(return_value='pipeline'),
            apply_vad_and_noise_reduction=Mock(return_value=self.compressed),
            transcribe_audio=Mock(return_value='Xin\n chao'),
        )
        self.words = [dict(word_index=0, text='Xin', start=.2, end=.4, score=.9, status='aligned')]

    def test_reuse_and_original_alignment(self):
        aligner = Mock()
        aligner.align.return_value = self.words
        with patch.multiple('stt3', **vars(self.backend)), \
             patch('stt3.VietnameseAligner', return_value=aligner) as factory:
            model = SpeechToTextModel()
            for _ in range(2):
                result = model.transcribe_audio(self.original, video_id='shared-id')
            self.backend.build_phowhisper_pipeline.assert_called_once()
            factory.assert_called_once()
            self.assertIs(self.backend.transcribe_audio.call_args.args[1], self.compressed)
            np.testing.assert_array_equal(aligner.align.call_args.args[1], self.original)
            self.assertEqual(result['text_train'], 'Xin chao')
            self.assertEqual(result['words'], self.words)
            self.assertEqual(result['video_id'], 'shared-id')
            json.dumps(result, allow_nan=False)

    def test_alignment_failure_preserves_text(self):
        model = SpeechToTextModel()
        model._aligner = Mock()
        model._aligner.align.side_effect = ValueError('test failure')
        with patch.multiple('stt3', **vars(self.backend)):
            result = model.transcribe_audio(self.original)
        self.assertEqual(result['status'], 'alignment_error')
        self.assertEqual(result['alignment_error'], 'test failure')
        self.assertEqual(result['text_train'], 'Xin chao')

    def test_text_only_does_not_load_aligner(self):
        model = SpeechToTextModel()
        with patch.multiple('stt3', **vars(self.backend)):
            result = model.transcribe_audio(self.original, align=False)
        self.assertIsNone(model._aligner)
        self.assertEqual(result['status'], 'transcribed')

    def test_empty_and_invalid_inputs(self):
        model = SpeechToTextModel()
        self.assertEqual(model.transcribe_audio([])['status'], 'no_transcript')
        self.assertIsNone(model._asr)
        for audio in ([[0, 0]], [float('nan')], [100]):
            with self.assertRaises(ValueError):
                model.transcribe_audio(audio)
        with self.assertRaises(ValueError):
            model.transcribe_audio([0], sample_rate=8000)
        with self.assertRaises(FileNotFoundError):
            model.transcribe('__nonexistent_test_video__.mp4')


if __name__ == '__main__':
    unittest.main()
