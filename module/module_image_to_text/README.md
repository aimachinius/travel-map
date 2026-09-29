# Phát hiện vùng chữ & Nhận diện chữ (Text Detection & Recognition)

Dự án này được trích xuất từ `deepdoc_vietocr` và được tích hợp thêm thư viện `vietocr`. 
Chức năng chính:
1. **Phát hiện vùng chữ (Text Detection):** Sử dụng mô hình PaddleOCR ONNX để khoanh vùng và cắt các đoạn text trên ảnh.
2. **Nhận diện chữ (OCR):** Tự động đưa các vùng ảnh vừa cắt vào mô hình `vgg_seq2seq` của VietOCR để đọc ra văn bản tiếng Việt.

Dự án hoàn toàn độc lập, bạn có thể copy toàn bộ thư mục `Phat_hien_vung_chu` đi nơi khác chạy bình thường.

## 1. Cài đặt

1. Đảm bảo bạn đã cài đặt Python 3.
2. Cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
```
*(Lưu ý: Mô hình VietOCR (`vgg_seq2seq.pth`) sẽ được tự động tải về thư mục cache ở lần chạy đầu tiên nếu chưa có).*

## 2. Cách sử dụng

Chạy file `main.py` qua command line, truyền vào đường dẫn ảnh (hoặc thư mục ảnh) qua tham số `--input` và thư mục xuất qua `--output`.

**Ví dụ:**
Chạy với một ảnh cụ thể:
```bash
python main.py --input "path/to/image.jpg" --output "output_folder"
```

Sau khi chạy xong, trong thư mục output của bạn sẽ xuất hiện:
- Các bức ảnh nhỏ (`..._crop_0.jpg`, `..._crop_1.jpg`) tương ứng với từng dòng chữ.
- Các file `.txt` tương ứng chứa nội dung chữ của từng bức ảnh nhỏ.
- Một file `..._full.txt` chứa toàn bộ văn bản đọc được từ ảnh gốc.
```bash
python main.py --input "path/to/image.jpg" --output "output_folder"
```

Chạy với một thư mục chứa nhiều ảnh:
```bash
python main.py --input "path/to/images_dir" --output "output_folder"
```

Sau khi chạy xong, trong thư mục output của bạn sẽ xuất hiện các bức ảnh nhỏ (ví dụ: `image_crop_0.jpg`, `image_crop_1.jpg`,...) tương ứng với các vùng chứa văn bản trong bức ảnh gốc.
