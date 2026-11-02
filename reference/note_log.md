/usr/local/lib/python3.13/dist-packages/moviepy/video/io/ffmpeg_reader.py:294: SyntaxWarning: invalid escape sequence '\d'
  lines_video = [l for l in lines if ' Video: ' in l and re.search('\d+x\d+', l)]
/usr/local/lib/python3.13/dist-packages/moviepy/video/io/ffmpeg_reader.py:367: SyntaxWarning: invalid escape sequence '\d'
  rotation_lines = [l for l in lines if 'rotate          :' in l and re.search('\d+$', l)]
/usr/local/lib/python3.13/dist-packages/moviepy/video/io/ffmpeg_reader.py:370: SyntaxWarning: invalid escape sequence '\d'
  match = re.search('\d+$', rotation_line)
/usr/local/lib/python3.13/dist-packages/moviepy/config_defaults.py:47: SyntaxWarning: invalid escape sequence '\P'
  IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-6.8.8-Q16\magick.exe"

=================================================================
🚀 ĐANG KHỞI CHẠY AI SERVER TRÍCH XUẤT QUÁN ĂN...
🏠 Cổng Local: http://127.0.0.1:8000
🌐 Cầu nối   : CLOUDFLARE
⚙️ Low-VRAM  : TẮT
=================================================================

[32mINFO[0m:     Started server process [[36m2383[0m]
[32mINFO[0m:     Waiting for application startup.
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: ============================================================
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: 🚀 [KHỞI ĐỘNG RESTAURANT EXTRACTION AI SERVER]
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: 📍 Cổng nội bộ: http://0.0.0.0:8000
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: ⚙️ Chế độ Low-VRAM: False
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: 🎤 Mô hình ASR: vinai/PhoWhisper-medium
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: 👁️ Mô hình VLM: 5CD-AI/Vintern-1B-v3_5
[2026-10-31 13:10:51] [INFO] [FastAPIServer]: ============================================================
[2026-10-31 13:10:53] [INFO] [ONNXTextDetector]: Đang nạp mô hình DBNet ONNX từ: /content/drive/MyDrive/colab/pbl/main/tham_khao/onnx/det.onnx (force_cpu=True)
[2026-10-31 13:10:55] [INFO] [ONNXTextDetector]: Đã nạp DBNet ONNX thành công trên CPU (CPUExecutionProvider)
[2026-10-31 13:10:55] [INFO] [ONNXTextDetector]: Khởi tạo ONNXTextDetector thành công (Hoàn toàn độc lập trong src/)!
[2026-10-31 13:10:55] [INFO] [TunnelManager]: Đang khởi động Cloudflare Tunnel cho cổng local 8000...
Download cloudflared...: 100% 38.4M/38.4M [00:00<00:00, 189MB/s]
 * Running on https://attribute-warranty-simple-cash.trycloudflare.com
 * Traffic stats available on http://127.0.0.1:20241/metrics
[2026-10-31 13:10:59] [INFO] [TunnelManager]: ============================================================
[2026-10-31 13:10:59] [INFO] [TunnelManager]: 🎉 [CẦU NỐI CLOUDFLARE TUNNEL THÀNH CÔNG!]
[2026-10-31 13:10:59] [INFO] [TunnelManager]: 🌐 Public URL (HTTPS): https://attribute-warranty-simple-cash.trycloudflare.com
[2026-10-31 13:10:59] [INFO] [TunnelManager]: 🏠 Local URL         : http://127.0.0.1:8000
[2026-10-31 13:10:59] [INFO] [TunnelManager]: ============================================================
[2026-10-31 13:10:59] [INFO] [FastAPIServer]: 🌐 Public API Endpoint: https://attribute-warranty-simple-cash.trycloudflare.com/api/v1/extract
[2026-10-31 13:10:59] [INFO] [FastAPIServer]: Đã kích hoạt tiến trình dọn rác định kỳ (chu kỳ 3600s).
[32mINFO[0m:     Application startup complete.
[32mINFO[0m:     Uvicorn running on [1mhttp://0.0.0.0:8000[0m (Press CTRL+C to quit)
[2026-10-31 13:11:11] [INFO] [ExtractRouter]: Bắt đầu xử lý đồng bộ URL: https://www.tiktok.com/@bachuareview/video/7109032785003695387
[2026-10-31 13:11:11] [INFO] [StorageManager]: Đã tìm thấy kết quả trong cache cho URL: https://www.tiktok.com/@bachuareview/video/7109032785003695387
[32mINFO[0m:     127.0.0.1:58494 - "[1mPOST /api/v1/extract HTTP/1.1[0m" [32m200 OK[0m
[2026-10-31 13:16:21] [INFO] [ExtractRouter]: Bắt đầu xử lý đồng bộ URL: https://www.tiktok.com/@bachuareview/video/7109032785003695387
[2026-10-31 13:16:21] [INFO] [VideoDownloader]: Bắt đầu tải video từ URL (tiktok): https://www.tiktok.com/@bachuareview/video/7109032785003695387
[K[2026-10-31 13:16:24] [INFO] [VideoDownloader]: Tải video thành công: /content/drive/MyDrive/colab/pbl/main/storage/videos/7109032785003695387.mp4 (8.96 MB trong 2.68s)
[2026-10-31 13:16:27] [INFO] [SpeechToTextEngine]: Đang nạp mô hình PhoWhisper từ 'vinai/PhoWhisper-medium' (CUDA=True)...
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1793452594.050123    3894 cpu_feature_guard.cc:227] This TensorFlow binary is optimized to use available CPU instructions in performance-critical operations.
To enable the following instructions: AVX2 AVX512F FMA, in other operations, rebuild TensorFlow with the appropriate compiler flags.
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1793452599.955652    3894 cudart_stub.cc:31] Could not find cuda drivers on your machine, GPU will not be used.
[ WARN:1@368.556] global cap.cpp:172 open VIDEOIO(CV_IMAGES): raised OpenCV exception:

OpenCV(4.14.0) /io/opencv/modules/videoio/src/cap_images.cpp:262: error: (-215:Assertion failed) number < max_number in function 'icvExtractPattern'


[2026-10-31 13:16:42] [ERROR] [TextKeyframeSelector]: OpenCV không thể mở video: /content/drive/MyDrive/colab/pbl/main/storage/videos/7109032785003695387.mp4
preprocessor_config.json: 100% 339/339 [00:00<00:00, 2.88MB/s]
tokenizer_config.json: 100% 805/805 [00:00<00:00, 6.85MB/s]
vocab.json: 836kB [00:00, 22.8MB/s]
tokenizer.json: 2.20MB [00:00, 111MB/s]
merges.txt: 494kB [00:00, 74.8MB/s]
normalizer.json: 52.7kB [00:00, 105MB/s]
added_tokens.json: 2.08kB [00:00, 10.8MB/s]
special_tokens_map.json: 2.08kB [00:00, 13.4MB/s]
config.json: 1.33kB [00:00, 7.12MB/s]
`torch_dtype` is deprecated! Use `dtype` instead!
pytorch_model.bin: 100% 3.06G/3.06G [00:41<00:00, 73.6MB/s]
generation_config.json: 3.72kB [00:00, 16.2MB/s]
Device set to use cuda:0
Using `chunk_length_s` is very experimental with seq2seq models. The results will not necessarily be entirely accurate and will have caveats. More information: https://github.com/huggingface/transformers/pull/20104. Ignore this warning with pipeline(..., ignore_warning=True). To use Whisper for long-form transcription, use rather the model's `generate` method directly as the model relies on it's own chunking mechanism (cf. Whisper original paper, section 3.8. Long-form Transcription).
[2026-10-31 13:17:30] [INFO] [SpeechToTextEngine]: Mô hình PhoWhisper-medium đã sẵn sàng hoạt động.
[2026-10-31 13:17:30] [INFO] [SpeechToTextEngine]: Đang phiên âm video (47.11s audio) bằng PhoWhisper-medium...
[2026-10-31 13:17:57] [INFO] [SpeechToTextEngine]: Phiên âm hoàn tất trong 93.16s: 'ơn giời bún ốc cô thủy đấy rồi đi qua năm chín cửa nam không thấy quán đâu tí kh...'
[2026-10-31 13:17:57] [INFO] [StorageManager]: Đã lưu 0 clean keyframes cho video 7109032785003695387 tại /content/drive/MyDrive/colab/pbl/main/storage/keyframes/7109032785003695387
[2026-10-31 13:17:57] [INFO] [ServerExtractionPipeline]: Đang khởi tạo Vintern1BExtractor cho Server Pipeline...
[2026-10-31 13:17:57] [INFO] [Vintern1BExtractor]: [*] Đang chuẩn bị nạp mô hình VLM: 5CD-AI/Vintern-1B-v3_5...
[2026-10-31 13:17:57] [INFO] [Vintern1BExtractor]: [*] Thiết bị: cuda | Kiểu dữ liệu: torch.bfloat16
config.json: 5.30kB [00:00, 18.0MB/s]
configuration_internvl_chat.py: 3.88kB [00:00, 2.36MB/s]
configuration_intern_vit.py: 5.55kB [00:00, 17.6MB/s]
A new version of the following files was downloaded from https://huggingface.co/5CD-AI/Vintern-1B-v3_5:
- configuration_intern_vit.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
A new version of the following files was downloaded from https://huggingface.co/5CD-AI/Vintern-1B-v3_5:
- configuration_internvl_chat.py
- configuration_intern_vit.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
modeling_internvl_chat.py: 15.6kB [00:00, 47.3MB/s]
conversation.py: 16.4kB [00:00, 57.7MB/s]
A new version of the following files was downloaded from https://huggingface.co/5CD-AI/Vintern-1B-v3_5:
- conversation.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
modeling_intern_vit.py: 18.1kB [00:00, 50.2MB/s]
A new version of the following files was downloaded from https://huggingface.co/5CD-AI/Vintern-1B-v3_5:
- modeling_intern_vit.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
A new version of the following files was downloaded from https://huggingface.co/5CD-AI/Vintern-1B-v3_5:
- modeling_internvl_chat.py
- conversation.py
- modeling_intern_vit.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
WARNING:py.warnings:/usr/local/lib/python3.13/dist-packages/timm/models/layers/__init__.py:49: FutureWarning: Importing from timm.models.layers is deprecated, please import via timm.layers
  warnings.warn(f"Importing from {__name__} is deprecated, please import via timm.layers", FutureWarning)

FlashAttention2 is not installed.
model.safetensors: 100% 3.75G/3.75G [03:15<00:00, 19.2MB/s]
generation_config.json: 100% 129/129 [00:00<00:00, 711kB/s]
tokenizer_config.json: 9.02kB [00:00, 3.71MB/s]
vocab.json: 3.38MB [00:00, 63.2MB/s]
merges.txt: 1.67MB [00:00, 124MB/s]
added_tokens.json: 100% 790/790 [00:00<00:00, 8.24MB/s]
special_tokens_map.json: 100% 744/744 [00:00<00:00, 7.24MB/s]
[2026-10-31 13:21:34] [INFO] [Vintern1BExtractor]: [✓] Nạp mô hình Vintern-1B và Tokenizer thành công!
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:21:36] [INFO] [Vintern1BExtractor]: [1. KHỞI TẠO NGỮ CẢNH] Video ID: 7109032785003695387
[2026-10-31 13:21:36] [INFO] [Vintern1BExtractor]:   • Tên quán tiềm năng (Text) : None
[2026-10-31 13:21:36] [INFO] [Vintern1BExtractor]:   • Địa chỉ tiềm năng (Text)  : None
[2026-10-31 13:21:36] [INFO] [Vintern1BExtractor]: 
[XỬ LÝ TUẦN TỰ 0 KHUNG HÌNH CHO VIDEO: 7109032785003695387]
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]: 🎯 KẾT LUẬN CUỐI CÙNG:
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]:   • Tên quán   : Chợ Bún Ốc Cô Thủy
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]:   • Địa chỉ    : 30 cửa nam, Cô thủy bán bún ốc hưng yên, 25-30 cành, 455 mươi cành
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]:   • Độ tin cậy : Trung bình
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]:   • Dẫn chứng  : {'nguồn_tên_quán': 'Lời thoại (Script)', 'nguồn_địa_chỉ': 'Lời thoại (Script)'}
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:21:40] [INFO] [Vintern1BExtractor]: [✓] Đã xóa sạch ngữ cảnh & dọn dẹp bộ nhớ GPU.

[2026-10-31 13:21:40] [WARNING] [StorageManager]: Lỗi khi lưu cache JSON /content/drive/MyDrive/colab/pbl/main/storage/cache/e0c328cb271287b45aab9ff0731ccaac.json: [Errno 2] No such file or directory: '/content/drive/MyDrive/colab/pbl/main/storage/cache/e0c328cb271287b45aab9ff0731ccaac.json'
[32mINFO[0m:     127.0.0.1:53508 - "[1mPOST /api/v1/extract HTTP/1.1[0m" [32m200 OK[0m
[2026-10-31 13:25:03] [INFO] [ExtractRouter]: Bắt đầu xử lý đồng bộ URL: https://www.tiktok.com/@bachuareview/video/7126014523596672282
[2026-10-31 13:25:03] [INFO] [VideoDownloader]: Bắt đầu tải video từ URL (tiktok): https://www.tiktok.com/@bachuareview/video/7126014523596672282
[K[2026-10-31 13:25:06] [INFO] [VideoDownloader]: Tải video thành công: /content/drive/MyDrive/colab/pbl/main/storage/videos/7126014523596672282.mp4 (9.01 MB trong 2.89s)
INFO:pyscenedetect:Detecting scenes...
[2026-10-31 13:25:09] [INFO] [SpeechToTextEngine]: Đang phiên âm video (52.59s audio) bằng PhoWhisper-medium...
[2026-10-31 13:25:58] [INFO] [SpeechToTextEngine]: Phiên âm hoàn tất trong 51.72s: 'quán đồ trung hoa bình dân đông khách nhất phố ngọc khánh mọi người đã thử chưa ...'
[2026-10-31 13:25:58] [INFO] [StorageManager]: Đã lưu 4 clean keyframes cho video 7126014523596672282 tại /content/drive/MyDrive/colab/pbl/main/storage/keyframes/7126014523596672282
[2026-10-31 13:25:58] [INFO] [StorageManager]: Đã xóa an toàn file: /content/drive/MyDrive/colab/pbl/main/storage/videos/7126014523596672282.mp4
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:00] [INFO] [Vintern1BExtractor]: [1. KHỞI TẠO NGỮ CẢNH] Video ID: 7126014523596672282
[2026-10-31 13:26:00] [INFO] [Vintern1BExtractor]:   • Tên quán tiềm năng (Text) : cô mi séc hôm một
[2026-10-31 13:26:00] [INFO] [Vintern1BExtractor]:   • Địa chỉ tiềm năng (Text)  : None
[2026-10-31 13:26:00] [INFO] [Vintern1BExtractor]: 
[XỬ LÝ TUẦN TỰ 4 KHUNG HÌNH CHO VIDEO: 7126014523596672282]
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:03] [INFO] [Vintern1BExtractor]:   [Frame 1/4] -> Tên OCR: HOME | Địa chỉ OCR: 34 Ngọc Khánh, Ba Đình | Chữ khác: None
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:07] [INFO] [Vintern1BExtractor]:   [Frame 2/4] -> Tên OCR: Phong Vị Việt | Địa chỉ OCR: Nhánh - Ba Đình - Hà Nội | Chữ khác: Phong Vị Việt
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:10] [INFO] [Vintern1BExtractor]:   [Frame 3/4] -> Tên OCR: GIEF HO | Địa chỉ OCR: 34 Ngọc Khánh - Ba Đình - Hà Nội | Chữ khác: None
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:13] [INFO] [Vintern1BExtractor]:   [Frame 4/4] -> Tên OCR: None | Địa chỉ OCR: None | Chữ khác: None
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]: 🎯 KẾT LUẬN CUỐI CÙNG:
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]:   • Tên quán   : Phong Vị Việt
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]:   • Địa chỉ    : 34 Ngọc Khánh - Ba Đình - Hà Nội
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]:   • Độ tin cậy : Cao
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]:   • Dẫn chứng  : {'nguồn_tên_quán': 'Frame 2 (OCR)', 'nguồn_địa_chỉ': 'Frame 3 (OCR)'}
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:26:15] [INFO] [Vintern1BExtractor]: [✓] Đã xóa sạch ngữ cảnh & dọn dẹp bộ nhớ GPU.

[2026-10-31 13:26:15] [WARNING] [StorageManager]: Lỗi khi lưu cache JSON /content/drive/MyDrive/colab/pbl/main/storage/cache/855cf194bc49f3c6d9efb2a66d1a17ca.json: [Errno 2] No such file or directory: '/content/drive/MyDrive/colab/pbl/main/storage/cache/855cf194bc49f3c6d9efb2a66d1a17ca.json'
[32mINFO[0m:     127.0.0.1:39882 - "[1mPOST /api/v1/extract HTTP/1.1[0m" [32m200 OK[0m
[2026-10-31 13:29:46] [INFO] [ExtractRouter]: Bắt đầu xử lý đồng bộ URL: https://www.tiktok.com/@lautombau17/video/7686850472472481045
[2026-10-31 13:29:46] [INFO] [VideoDownloader]: Bắt đầu tải video từ URL (tiktok): https://www.tiktok.com/@lautombau17/video/7686850472472481045
[K[2026-10-31 13:29:48] [INFO] [VideoDownloader]: Tải video thành công: /content/drive/MyDrive/colab/pbl/main/storage/videos/7686850472472481045.mp4 (3.2 MB trong 1.45s)
INFO:pyscenedetect:Detecting scenes...
[2026-10-31 13:29:48] [INFO] [SpeechToTextEngine]: Đang phiên âm video (17.07s audio) bằng PhoWhisper-medium...
[2026-10-31 13:29:54] [INFO] [SpeechToTextEngine]: Phiên âm hoàn tất trong 6.14s: 'anh ôn em đây em đây chiều rừng buôn tặng trường anh đến để chờ đằng thơ đi học ...'
[2026-10-31 13:30:30] [INFO] [StorageManager]: Đã lưu 4 clean keyframes cho video 7686850472472481045 tại /content/drive/MyDrive/colab/pbl/main/storage/keyframes/7686850472472481045
[2026-10-31 13:30:30] [INFO] [StorageManager]: Đã xóa an toàn file: /content/drive/MyDrive/colab/pbl/main/storage/videos/7686850472472481045.mp4
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:31] [INFO] [Vintern1BExtractor]: [1. KHỞI TẠO NGỮ CẢNH] Video ID: 7686850472472481045
[2026-10-31 13:30:31] [INFO] [Vintern1BExtractor]:   • Tên quán tiềm năng (Text) : None
[2026-10-31 13:30:31] [INFO] [Vintern1BExtractor]:   • Địa chỉ tiềm năng (Text)  : None
[2026-10-31 13:30:31] [INFO] [Vintern1BExtractor]: 
[XỬ LÝ TUẦN TỰ 4 KHUNG HÌNH CHO VIDEO: 7686850472472481045]
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:35] [INFO] [Vintern1BExtractor]:   [Frame 1/4] -> Tên OCR: Lẩu Tôm Bầu | Địa chỉ OCR: 17 Đống Đa, Đà Nẵng | Chữ khác: Buffet nướng lẩu tôm bầu
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:38] [INFO] [Vintern1BExtractor]:   [Frame 2/4] -> Tên OCR: Buffet Nướng 159k | Địa chỉ OCR: None | Chữ khác: None
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:42] [INFO] [Vintern1BExtractor]:   [Frame 3/4] -> Tên OCR: Buffet Nướng 159k | Địa chỉ OCR: None | Chữ khác: Dành cho couple ngày mưa
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:44] [INFO] [Vintern1BExtractor]:   [Frame 4/4] -> Tên OCR: None | Địa chỉ OCR: None | Chữ khác: None
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]: 🎯 KẾT LUẬN CUỐI CÙNG:
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]:   • Tên quán   : Buffet Nướng 159k
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]:   • Địa chỉ    : 17 Đống Đa, Đà Nẵng
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]:   • Độ tin cậy : Cao
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]:   • Dẫn chứng  : {'nguồn_tên_quán': 'Frame 2 (OCR)', 'nguồn_địa_chỉ': 'Frame 1 (OCR)'}
[2026-10-31 13:30:46] [INFO] [Vintern1BExtractor]: ==================================================
[2026-10-31 13:30:47] [INFO] [Vintern1BExtractor]: [✓] Đã xóa sạch ngữ cảnh & dọn dẹp bộ nhớ GPU.

[2026-10-31 13:30:47] [WARNING] [StorageManager]: Lỗi khi lưu cache JSON /content/drive/MyDrive/colab/pbl/main/storage/cache/1d53f9b7b0cab934186134b8597eabf1.json: [Errno 2] No such file or directory: '/content/drive/MyDrive/colab/pbl/main/storage/cache/1d53f9b7b0cab934186134b8597eabf1.json'
[32mINFO[0m:     127.0.0.1:44028 - "[1mPOST /api/v1/extract HTTP/1.1[0m" [32m200 OK[0m
[32mINFO[0m:     Shutting down
[32mINFO[0m:     Waiting for application shutdown.
[2026-10-31 13:32:32] [INFO] [FastAPIServer]: Đang dừng AI Server...
[2026-10-31 13:32:32] [INFO] [TunnelManager]: Đã đóng Cloudflare Tunnel.
[2026-10-31 13:32:32] [INFO] [FastAPIServer]: AI Server đã dừng an toàn.
[2026-10-31 13:32:32] [INFO] [FastAPIServer]: Tiến trình dọn rác định kỳ đã dừng.
[32mINFO[0m:     Application shutdown complete.
[32mINFO[0m:     Finished server process [[36m2383[0m]
