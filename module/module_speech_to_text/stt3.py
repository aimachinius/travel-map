"""Reusable STT component: media -> STT1 text + original-time word alignment.

Integration (create once, reuse for multiple videos):
    model = SpeechToTextModel(device="cpu")
    result = model.transcribe("video.mp4", video_id="video_001")
    # result["text_train"] -> full text; result["words"] -> timed words

This is the speech component, not a trained caption/OCR fusion model.
Standalone Python file. Requires FFmpeg and third-party packages:
    python -m pip install numpy torch transformers accelerate noisereduce webrtcvad-wheels yt-dlp
Model weights are downloaded on first use; no Excel or other project files needed.
"""

import argparse
from contextlib import redirect_stdout
import hashlib
import json
import logging
import math
import unicodedata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import RLock
from time import perf_counter
from urllib.parse import urlsplit

import numpy as np

os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "1"
LOGGER = logging.getLogger(__name__)


DEFAULT_ALIGN_MODEL = "nguyenvulebinh/wav2vec2-base-vietnamese-250h"
SAMPLE_RATE = 16000


def apply_vad_and_noise_reduction(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    import noisereduce as nr
    import webrtcvad
    if audio.size == 0:
        return audio

    # Use the opening 0.5 seconds as a conservative noise profile.
    noise_sample = audio[: min(len(audio), int(sample_rate * 0.5))]
    denoised = nr.reduce_noise(
        y=audio,
        sr=sample_rate,
        y_noise=noise_sample,
        stationary=True,
        prop_decrease=0.8,
    )

    pcm = np.clip(denoised * 32767, -32768, 32767).astype(np.int16)
    vad = webrtcvad.Vad(2)
    frame_size = int(sample_rate * 0.03)
    voiced_frames = []

    for start in range(0, len(pcm), frame_size):
        frame = pcm[start : start + frame_size]
        if len(frame) < frame_size:
            frame = np.pad(frame, (0, frame_size - len(frame)))
        if vad.is_speech(frame.tobytes(), sample_rate):
            voiced_frames.append(frame)

    if not voiced_frames:
        return denoised

    return np.concatenate(voiced_frames).astype(np.float32) / 32767.0


def build_phowhisper_pipeline(model_id: str, device: str):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    use_cuda = device == "cuda" and torch.cuda.is_available()
    torch_device = "cuda" if use_cuda else "cpu"
    pipeline_device = 0 if use_cuda else -1
    dtype = torch.float16 if use_cuda else torch.float32

    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        dtype=dtype,
        low_cpu_mem_usage=True,
        use_safetensors=False,
    )
    model.to(torch_device)

    return pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        chunk_length_s=30,
        device=pipeline_device,
    )


def transcribe_audio(asr_pipeline, audio: np.ndarray, sample_rate: int) -> str:
    if audio.size == 0:
        return ""

    result = asr_pipeline(
        {"raw": audio, "sampling_rate": sample_rate},
        generate_kwargs={"task": "transcribe", "language": "vi"},
    )
    return str(result.get("text", "")).strip()


def download_video(url: str, download_dir: Path, video_id: str) -> Path:
    from yt_dlp import YoutubeDL
    download_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(download_dir / f"{video_id}.%(ext)s")

    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "restrictfilenames": True,
    }

    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        prepared_path = Path(downloader.prepare_filename(info))

    if prepared_path.exists():
        return prepared_path

    candidates = list(download_dir.glob(f"{video_id}.*"))
    if not candidates:
        raise FileNotFoundError(f"Downloaded file not found for {url}")
    return candidates[0]


def ctc_path(log_probs, tokens, blank_id):
    """Viterbi path through blank/label CTC states, including repeated labels.

    Keep only two score rows and byte-sized backpointers. Audio frames are never
    removed, including leading/trailing silence. No text-length time estimates.
    """
    frames = len(log_probs)
    if not tokens:
        return np.full(frames, -1, dtype=np.int32)
    labels = np.full(2 * len(tokens) + 1, blank_id, dtype=np.int32)
    labels[1::2] = tokens
    states = len(labels)
    if frames < len(tokens) + sum(a == b for a, b in zip(tokens, tokens[1:])):
        raise ValueError("Transcript has too many characters for the audio frames.")
    if frames * states > 250_000_000:
        raise ValueError("Alignment is too large; process a shorter source video.")
    back = np.zeros((frames, states), dtype=np.uint8)
    prev = np.full(states, -np.inf, dtype=np.float32)
    prev[0] = log_probs[0, blank_id]
    prev[1] = log_probs[0, labels[1]]
    skip = np.zeros(states, dtype=bool)
    skip[2:] = (labels[2:] != blank_id) & (labels[2:] != labels[:-2])
    for t in range(1, frames):
        best = prev.copy()
        step = np.zeros(states, dtype=np.uint8)
        better = prev[:-1] > best[1:]
        best[1:] = np.where(better, prev[:-1], best[1:])
        step[1:] = better.astype(np.uint8)
        better = skip[2:] & (prev[:-2] > best[2:])
        best[2:] = np.where(better, prev[:-2], best[2:])
        step[2:] = np.where(better, 2, step[2:])
        prev = best + log_probs[t, labels]
        back[t] = step
    state = states - 1 if prev[-1] >= prev[-2] else states - 2
    if not np.isfinite(prev[state]):
        raise ValueError("No valid CTC alignment path for this transcript.")
    path = np.full(frames, -1, dtype=np.int32)
    for t in range(frames - 1, -1, -1):
        if state % 2:
            path[t] = state // 2
        state -= int(back[t, state])
    return path


def prepare_tokens(text, tokenizer):
    """Preserve displayed words; normalize only alignment characters.

    Vietnamese 'words' here mean whitespace-delimited units (often syllables).
    Digits/foreign letters absent from the vocabulary are flagged, not invented.
    """
    words = text.split()
    vocab = tokenizer.get_vocab()
    separator = tokenizer.word_delimiter_token_id
    tokens, owners, unsupported = [], [], []
    for index, word in enumerate(words):
        if tokens and separator is not None:
            tokens.append(separator)
            owners.append(-1)
        missing = False
        for char in unicodedata.normalize("NFC", word).lower():
            if char in vocab and vocab[char] not in tokenizer.all_special_ids:
                tokens.append(vocab[char])
                owners.append(index)
            elif char.isalnum():
                missing = True
        unsupported.append(missing)
    return words, tokens, owners, unsupported


class VietnameseAligner:
    def __init__(self, device="cpu", model_id=DEFAULT_ALIGN_MODEL, cache_dir=None):
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

        self.device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
        self.processor = Wav2Vec2Processor.from_pretrained(model_id, cache_dir=cache_dir)
        self.model = Wav2Vec2ForCTC.from_pretrained(
            model_id, cache_dir=cache_dir,
        ).to(self.device).eval()
        self.blank_id = self.model.config.pad_token_id

    def emissions(self, audio):
        import torch

        # Process 20-second cores with one second of acoustic context on each
        # side. Keep only core emissions and their original sample positions.
        core_size, context = 20 * SAMPLE_RATE, SAMPLE_RATE
        parts, times = [], []
        stride = math.prod(self.model.config.conv_stride)
        receptive = 1
        jump = 1
        for kernel, step in zip(self.model.config.conv_kernel, self.model.config.conv_stride):
            receptive += (kernel - 1) * jump
            jump *= step
        for core_start in range(0, len(audio), core_size):
            core_end = min(core_start + core_size, len(audio))
            left = max(0, core_start - context)
            right = min(len(audio), core_end + context)
            segment = audio[left:right]
            if len(segment) < receptive:
                segment = np.pad(segment, (0, receptive - len(segment)))
            inputs = self.processor(segment, sampling_rate=SAMPLE_RATE, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.inference_mode():
                probs = self.model(**inputs).logits[0].float().log_softmax(-1).cpu().numpy()
            centers = left + np.arange(len(probs)) * stride + receptive / 2
            keep = (centers >= core_start) & (centers < core_end)
            if not np.any(keep) and len(audio) < receptive:
                centers[0] = len(audio) / 2
                keep[0] = True
            parts.append(probs[keep])
            times.append(centers[keep] / SAMPLE_RATE)
        return np.concatenate(parts), np.concatenate(times), stride / SAMPLE_RATE

    def align(self, text, audio, sample_rate=SAMPLE_RATE):
        if sample_rate != SAMPLE_RATE:
            raise ValueError("Alignment requires original audio at 16000 Hz.")
        words, tokens, owners, unsupported = prepare_tokens(text, self.processor.tokenizer)
        rows = [dict(word_index=i, text=w, start=None, end=None, score=None,
                     status="unaligned") for i, w in enumerate(words)]
        if not tokens or len(audio) == 0:
            return rows
        probs, centers, step = self.emissions(audio)
        path = ctc_path(probs, tokens, self.blank_id)
        frames_by_word = [[] for _ in words]
        for frame, token_index in enumerate(path):
            if token_index >= 0 and owners[token_index] >= 0:
                frames_by_word[owners[token_index]].append(frame)
        duration = len(audio) / sample_rate
        for index, frames in enumerate(frames_by_word):
            if not frames:
                continue
            scores = [probs[f, tokens[path[f]]] for f in frames]
            score = float(np.exp(np.mean(scores)))
            rows[index].update(
                start=round(max(0.0, centers[frames[0]] - step / 2), 4),
                end=round(min(duration, centers[frames[-1]] + step / 2), 4),
                score=round(score, 4),
                status="review" if unsupported[index] or score < 0.3 else "aligned",
            )
        return rows


def words_in_window(words, start_time, end_time):
    """Select intervals overlapping a caller-supplied frame context window.

    This optional lookup does not modify timestamps or assign words to frames.
    The caller decides the window once actual frame timestamps are available.
    Intervals use [start, end); merely touching a boundary is not overlap.
    """
    if not (math.isfinite(start_time) and math.isfinite(end_time)
            and 0 <= start_time < end_time):
        raise ValueError("Window must have finite times with 0 <= start < end.")
    matches = []
    for word in words:
        start, end = word.get("start"), word.get("end")
        if start is None or end is None:
            continue
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
            raise ValueError("Word timestamps are outside the original audio timeline.")
        if start < end and start < end_time and end > start_time:
            matches.append(dict(word))
    return matches


class SpeechToTextModel:
    """Load models once; serialize calls on this instance for safe reuse.

    Transcribe errors raise exceptions. Alignment errors preserve recognized
    text and return status='alignment_error' with an explicit error message.
    The caller supplies the same video_id as the caption/OCR components.
    """

    def __init__(self, device="cpu", model_id="vinai/PhoWhisper-small",
                 align_model_id="nguyenvulebinh/wav2vec2-base-vietnamese-250h",
                 cache_dir=".cache/alignment"):
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")
        self.device = device
        self.model_id = model_id
        self.align_model_id = align_model_id
        self.cache_dir = str(cache_dir)
        self._asr = None
        self._aligner = None
        self._lock = RLock()

    def load(self, align=True):
        """Optional warmup. transcribe() also loads models when first needed."""
        with self._lock:
            if self._asr is None:
                LOGGER.info("Loading PhoWhisper...")
                self._asr = build_phowhisper_pipeline(self.model_id, self.device)
            if align and self._aligner is None:
                LOGGER.info("Loading Vietnamese alignment model...")
                self._aligner = VietnameseAligner(self.device, self.align_model_id, self.cache_dir)
        return self

    @staticmethod
    def _read_audio(path):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg is not installed or is not in PATH.")
        # Match STT2's mono 16 kHz signed-16-bit conversion, using memory
        # instead of an intermediate WAV or Excel file.
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
             "-ar", "16000", "-f", "s16le", "pipe:1"], capture_output=True,
        )
        if result.returncode:
            raise RuntimeError("FFmpeg failed: " + result.stderr.decode("utf-8", errors="replace"))
        return np.frombuffer(result.stdout, dtype="<i2").astype(np.float32) / 32768.0

    def transcribe(self, source, *, video_id=None, align=True):
        """Accept a local media path or HTTP(S) video URL; return a Python dict.

        Times start at zero in the supplied media. For matching frames, use
        exactly the same video cut/speed. No per-second text grouping is done.
        """
        source = str(source)
        is_url = urlsplit(source).scheme.lower() in {"http", "https"}
        if not is_url and not Path(source).is_file():
            raise FileNotFoundError(f"Media file not found: {source}")
        key = source if is_url else str(Path(source).resolve())
        identifier = video_id if video_id is not None else "video_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        started = perf_counter()
        if is_url:
            with tempfile.TemporaryDirectory(prefix="stt3_") as folder:
                # Use a fixed safe filename; video_id is metadata, never a path.
                media = download_video(source, Path(folder), "media")
                audio = self._read_audio(media)
        else:
            audio = self._read_audio(source)
        decoding_seconds = perf_counter() - started
        result = self.transcribe_audio(audio, video_id=identifier, align=align)
        result["source"] = source
        result["timings_seconds"]["download_decode"] = round(decoding_seconds, 3)
        return result

    def transcribe_audio(self, audio, *, sample_rate=16000, video_id=None, align=True):
        """Accept mono float audio at 16 kHz in [-1, 1], on its original timeline."""
        audio = np.array(audio, dtype=np.float32, copy=True)
        if sample_rate != 16000 or audio.ndim != 1:
            raise ValueError("Pass mono audio at 16000 Hz; use transcribe(path) for automatic conversion.")
        if not np.all(np.isfinite(audio)) or (audio.size and np.max(np.abs(audio)) > 1):
            raise ValueError("Audio must contain finite floating-point samples in [-1, 1].")
        result = {
            "schema_version": 1, "video_id": video_id, "source": None,
            "duration": len(audio) / 16000, "sample_rate": 16000,
            "time_origin": "start of supplied media, seconds from 0",
            "text": "", "text_train": "", "words": [],
            "status": "no_transcript", "review_count": 0,
            "alignment_error": None, "timings_seconds": {},
        }
        if not audio.size:
            return result
        with self._lock:
            started = perf_counter()
            self.load(align=False)
            result["timings_seconds"]["asr_load"] = round(perf_counter() - started, 3)
            started = perf_counter()
            LOGGER.info("Recognizing %.1fs of original audio with STT1 settings...", result["duration"])
            processed = apply_vad_and_noise_reduction(audio, 16000)
            text = transcribe_audio(self._asr, processed, 16000)
            result.update(text=text, text_train=" ".join(text.split()))
            result["timings_seconds"]["recognition"] = round(perf_counter() - started, 3)
            if not text.strip():
                return result
            result["status"] = "transcribed"
            if align:
                started = perf_counter()
                try:
                    self.load(align=True)
                    LOGGER.info("Aligning recognized words to original audio...")
                    words = self._aligner.align(text, audio, 16000)
                    review = sum(word["status"] != "aligned" for word in words)
                    result.update(words=words, review_count=review,
                                  status="review" if review else "aligned")
                except Exception as error:
                    result.update(status="alignment_error", alignment_error=str(error))
                    LOGGER.warning("Alignment failed; transcript preserved: %s", error)
                result["timings_seconds"]["alignment_including_load"] = round(perf_counter() - started, 3)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="Local media path or URL; omit to paste it interactively")
    parser.add_argument("--video-id", help="Shared ID used by caption/OCR components")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--no-align", action="store_true", help="Return text only; skip word alignment")
    parser.add_argument("--output", type=Path, help="Optional JSON file; default prints JSON")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        interactive = args.source is None
        if interactive:
            args.source = input("Dan link video (hoac duong dan file) roi nhan Enter: ").strip()
            if len(args.source) >= 2 and args.source[0] == args.source[-1] and args.source[0] in {'\"', "'"}:
                args.source = args.source[1:-1].strip()
            if not args.source:
                LOGGER.error("Chua nhap link/video. Chay lai va dan link de xu ly.")
                return 1
            if args.output is None:
                from datetime import datetime
                args.output = Path("stt3_results") / (datetime.now().strftime("result_%Y%m%d_%H%M%S_%f") + ".json")
        # Keep stdout valid JSON even if third-party libraries print progress.
        with redirect_stdout(sys.stderr):
            model = SpeechToTextModel(device=args.device)
            result = model.transcribe(args.source, video_id=args.video_id, align=not args.no_align)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
            if interactive:
                print("\nText:\n" + result["text_train"])
                print("\nTrang thai: " + result["status"])
                print("Da luu ket qua: " + str(args.output.resolve()))
        else:
            print(payload)
        return 2 if result["status"] == "alignment_error" else 0
    except (KeyboardInterrupt, EOFError):
        LOGGER.info("Da dung.")
        return 130
    except Exception as error:
        LOGGER.error("STT failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
