import argparse
import copy
import time
import os
import cv2
import numpy as np
import onnxruntime as ort
import matplotlib.pyplot as plt
from PIL import Image

from module.postprocess import build_post_process
from module import operators

from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

def transform(data, ops=None):
    if ops is None:
        ops = []
    for op in ops:
        data = op(data)
        if data is None:
            return None
    return data

def create_operators(op_param_list, global_config=None):
    assert isinstance(
        op_param_list, list), ('operator config should be a list')
    ops = []
    for operator in op_param_list:
        assert isinstance(operator, dict) and len(operator) == 1, "yaml format error"
        op_name = list(operator)[0]
        param = {} if operator[op_name] is None else operator[op_name]
        if global_config is not None:
            param.update(global_config)
        op = getattr(operators, op_name)(**param)
        ops.append(op)
    return ops

def load_model(model_dir, nm, device_id=None):
    model_file_path = os.path.join(model_dir, nm + ".onnx")
    
    if not os.path.exists(model_file_path):
        raise ValueError("not find model file path {}".format(
            model_file_path))

    def cuda_is_available():
        try:
            import torch
            if torch.cuda.is_available() and (device_id is None or torch.cuda.device_count() > device_id):
                return True
        except Exception:
            return False
        return False

    options = ort.SessionOptions()
    options.enable_cpu_mem_arena = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 2

    run_options = ort.RunOptions()
    if cuda_is_available():
        cuda_provider_options = {
            "device_id": device_id if device_id is not None else 0,
            "gpu_mem_limit": 512 * 1024 * 1024,
            "arena_extend_strategy": "kNextPowerOfTwo",
        }
        sess = ort.InferenceSession(
            model_file_path,
            options=options,
            providers=['CUDAExecutionProvider'],
            provider_options=[cuda_provider_options]
            )
        run_options.add_run_config_entry("memory.enable_memory_arena_shrinkage", "gpu:" + str(device_id if device_id is not None else 0))
    else:
        sess = ort.InferenceSession(
            model_file_path,
            options=options,
            providers=['CPUExecutionProvider'])
        run_options.add_run_config_entry("memory.enable_memory_arena_shrinkage", "cpu")
    
    return (sess, run_options)


class TextDetector:
    def __init__(self, model_dir, device_id=None):
        pre_process_list = [{
            'DetResizeForTest': {
                'limit_side_len': 960,
                'limit_type': "max",
            }
        }, {
            'NormalizeImage': {
                'std': [0.229, 0.224, 0.225],
                'mean': [0.485, 0.456, 0.406],
                'scale': '1./255.',
                'order': 'hwc'
            }
        }, {
            'ToCHWImage': None
        }, {
            'KeepKeys': {
                'keep_keys': ['image', 'shape']
            }
        }]
        postprocess_params = {"name": "DBPostProcess", "thresh": 0.3, "box_thresh": 0.5, "max_candidates": 1000,
                              "unclip_ratio": 2, "use_dilation": False, "score_mode": "fast", "box_type": "quad"}

        self.postprocess_op = build_post_process(postprocess_params)
        self.predictor, self.run_options = load_model(model_dir, 'det', device_id)
        self.input_tensor = self.predictor.get_inputs()[0]

        img_h, img_w = self.input_tensor.shape[2:]
        if isinstance(img_h, str) or isinstance(img_w, str):
            pass
        elif img_h is not None and img_w is not None and img_h > 0 and img_w > 0:
            pre_process_list[0] = {
                'DetResizeForTest': {
                    'image_shape': [img_h, img_w]
                }
            }
        self.preprocess_op = create_operators(pre_process_list)

    def order_points_clockwise(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        tmp = np.delete(pts, (np.argmin(s), np.argmax(s)), axis=0)
        diff = np.diff(np.array(tmp), axis=1)
        rect[1] = tmp[np.argmin(diff)]
        rect[3] = tmp[np.argmax(diff)]
        return rect

    def clip_det_res(self, points, img_height, img_width):
        for pno in range(points.shape[0]):
            points[pno, 0] = int(min(max(points[pno, 0], 0), img_width - 1))
            points[pno, 1] = int(min(max(points[pno, 1], 0), img_height - 1))
        return points

    def filter_tag_det_res(self, dt_boxes, image_shape):
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            if isinstance(box, list):
                box = np.array(box)
            box = self.order_points_clockwise(box)
            box = self.clip_det_res(box, img_height, img_width)
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3:
                continue
            dt_boxes_new.append(box)
        dt_boxes = np.array(dt_boxes_new)
        return dt_boxes

    def __call__(self, img):
        ori_im = img.copy()
        data = {'image': img}

        data = transform(data, self.preprocess_op)
        img_pre, shape_list = data
        if img_pre is None:
            return None, None
        img_pre = np.expand_dims(img_pre, axis=0)
        shape_list = np.expand_dims(shape_list, axis=0)
        
        input_dict = {self.input_tensor.name: img_pre.copy()}
        for i in range(10):
            try:
                outputs = self.predictor.run(None, input_dict, self.run_options)
                break
            except Exception as e:
                if i >= 3:
                    raise e
                time.sleep(1)

        post_result = self.postprocess_op({"maps": outputs[0]}, shape_list)
        dt_boxes = post_result[0]['points']
        dt_boxes = self.filter_tag_det_res(dt_boxes, ori_im.shape)

        # Trích xuất Heatmap (Probability Map) - Bước 3
        pred = outputs[0][0, 0, :, :] # shape (map_H, map_W)
        
        # Thresholding (Bước 4)
        thresh = 0.3
        mask = (pred > thresh).astype(np.uint8) * 255
        
        # Resize mask về kích thước ảnh gốc
        src_h, src_w = ori_im.shape[:2]
        mask_resized = cv2.resize(mask, (src_w, src_h), interpolation=cv2.INTER_NEAREST)
        
        # Xử lý hình thái học (Bước 5)
        # Giãn nở (Dilation) để khôi phục nét chữ từ lõi
        kernel = np.ones((3,3), np.uint8)
        mask_dilated = cv2.dilate(mask_resized, kernel, iterations=1)
        
        # Nghịch đảo màu (Bước 6) - Chữ đen trên nền trắng
        mask_inverted = cv2.bitwise_not(mask_dilated)
        
        # Chuyển về 3 kênh màu để có thể dùng hàm crop như ảnh RGB bình thường
        mask_final = cv2.cvtColor(mask_inverted, cv2.COLOR_GRAY2BGR)

        return dt_boxes, mask_final


def get_rotate_crop_image(img, points):
    assert len(points) == 4, "shape of points must be 4*2"
    img_crop_width = int(
        max(
            np.linalg.norm(points[0] - points[1]),
            np.linalg.norm(points[2] - points[3])))
    img_crop_height = int(
        max(
            np.linalg.norm(points[0] - points[3]),
            np.linalg.norm(points[1] - points[2])))
    pts_std = np.float32([[0, 0], [img_crop_width, 0],
                          [img_crop_width, img_crop_height],
                          [0, img_crop_height]])
    M = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        M, (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC)
    dst_img_height, dst_img_width = dst_img.shape[0:2]
    if dst_img_height * 1.0 / dst_img_width >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


def sorted_boxes(dt_boxes):
    num_boxes = dt_boxes.shape[0]
    sorted_boxes = sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0]))
    _boxes = list(sorted_boxes)

    for i in range(num_boxes - 1):
        for j in range(i, -1, -1):
            if abs(_boxes[j + 1][0][1] - _boxes[j][0][1]) < 10 and \
                    (_boxes[j + 1][0][0] < _boxes[j][0][0]):
                tmp = _boxes[j]
                _boxes[j] = _boxes[j + 1]
                _boxes[j + 1] = tmp
            else:
                break
    return _boxes

def load_recognizer():
    config = Cfg.load_config_from_name('vgg_transformer')
    config['cnn']['pretrained'] = False 
    config['device'] = 'cpu'
    
    try:
        import torch
        if torch.cuda.is_available():
            config['device'] = 'cuda:0'
            print("VietOCR uses GPU.")
    except Exception:
        pass
        
    detector = Predictor(config)
    return detector

def process_image(img_path, output_dir, detector, recognizer):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Cannot read image: {img_path}")
        return
    
    # PaddleOCR uses RGB for detection pre-processing
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Lấy cả bounding boxes VÀ binary mask từ Deep Learning model
    dt_boxes, mask_final = detector(img_rgb)
    if dt_boxes is None or len(dt_boxes) == 0:
        print(f"No text found in {img_path}")
        return
        
    dt_boxes = sorted_boxes(dt_boxes)
    
    base_name = os.path.basename(img_path)
    name, ext = os.path.splitext(base_name)
    
    full_text = []
    
    # Lưu lại ảnh mask_final tổng để kiểm tra
    cv2.imwrite(os.path.join(output_dir, f"{name}_dl_mask_full.jpg"), mask_final)
    
    for idx, box in enumerate(dt_boxes):
        # Crop trên ảnh gốc (để xem)
        crop_img_raw = get_rotate_crop_image(img, box) 
        
        # Crop trên ảnh MASK NHỊ PHÂN (để OCR)
        crop_img_mask = get_rotate_crop_image(mask_final, box)
        
        out_name = f"{name}_crop_{idx}{ext}"
        out_path = os.path.join(output_dir, out_name)
        
        # Lưu cả 2 để so sánh
        cv2.imwrite(os.path.join(output_dir, f"{name}_crop_{idx}_raw{ext}"), crop_img_raw)
        cv2.imwrite(out_path, crop_img_mask)
        
        # Chạy OCR trên ảnh MASK NHỊ PHÂN
        pil_img = Image.fromarray(cv2.cvtColor(crop_img_mask, cv2.COLOR_BGR2RGB))
        text = recognizer.predict(pil_img)
        full_text.append(text)
        
        txt_path = os.path.join(output_dir, f"{name}_crop_{idx}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
            
    with open(os.path.join(output_dir, f"{name}_full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))
        
    print(f"Processed {img_path}: saved {len(dt_boxes)} cropped regions to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Deep Learning Mask Text Detection & Recognition")
    parser.add_argument("--input", required=True, help="Path to input image or directory")
    parser.add_argument("--output", default="output", help="Directory to save cropped images and text")
    parser.add_argument("--model_dir", default="onnx", help="Directory containing det.onnx")
    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)
        
    print("Loading Detection Model...")
    detector = TextDetector(model_dir=args.model_dir)
    
    print("Loading VietOCR Model...")
    recognizer = load_recognizer()
    
    if os.path.isdir(args.input):
        for filename in os.listdir(args.input):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                img_path = os.path.join(args.input, filename)
                process_image(img_path, args.output, detector, recognizer)
    else:
        process_image(args.input, args.output, detector, recognizer)

if __name__ == "__main__":
    main()
