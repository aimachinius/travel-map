import argparse
import copy
import time
import os
import cv2
import numpy as np
import onnxruntime as ort
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
    assert isinstance(op_param_list, list), ('operator config should be a list')
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
        raise ValueError("not find model file path {}".format(model_file_path))

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
            model_file_path, options=options, providers=['CUDAExecutionProvider'], provider_options=[cuda_provider_options])
    else:
        sess = ort.InferenceSession(model_file_path, options=options, providers=['CPUExecutionProvider'])
    return (sess, run_options)

class TextDetector:
    def __init__(self, model_dir, device_id=None):
        pre_process_list = [{'DetResizeForTest': {'limit_side_len': 960, 'limit_type': "max"}},
                            {'NormalizeImage': {'std': [0.229, 0.224, 0.225], 'mean': [0.485, 0.456, 0.406], 'scale': '1./255.', 'order': 'hwc'}},
                            {'ToCHWImage': None},
                            {'KeepKeys': {'keep_keys': ['image', 'shape']}}]
        postprocess_params = {"name": "DBPostProcess", "thresh": 0.3, "box_thresh": 0.5, "max_candidates": 1000,
                              "unclip_ratio": 2, "use_dilation": False, "score_mode": "fast", "box_type": "quad"}

        self.postprocess_op = build_post_process(postprocess_params)
        self.predictor, self.run_options = load_model(model_dir, 'det', device_id)
        self.input_tensor = self.predictor.get_inputs()[0]
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

    def filter_tag_det_res(self, dt_boxes, image_shape):
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            box = self.order_points_clockwise(np.array(box))
            for pno in range(box.shape[0]):
                box[pno, 0] = int(min(max(box[pno, 0], 0), img_width - 1))
                box[pno, 1] = int(min(max(box[pno, 1], 0), img_height - 1))
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3: continue
            dt_boxes_new.append(box)
        return np.array(dt_boxes_new)

    def __call__(self, img):
        ori_im = img.copy()
        data = transform({'image': img}, self.preprocess_op)
        if data[0] is None: return None
        img_pre = np.expand_dims(data[0], axis=0)
        shape_list = np.expand_dims(data[1], axis=0)
        
        outputs = self.predictor.run(None, {self.input_tensor.name: img_pre.copy()}, self.run_options)
        post_result = self.postprocess_op({"maps": outputs[0]}, shape_list)
        return self.filter_tag_det_res(post_result[0]['points'], ori_im.shape)

def get_rotate_crop_image(img, points):
    img_crop_width = int(max(np.linalg.norm(points[0]-points[1]), np.linalg.norm(points[2]-points[3])))
    img_crop_height = int(max(np.linalg.norm(points[0]-points[3]), np.linalg.norm(points[1]-points[2])))
    pts_std = np.float32([[0, 0], [img_crop_width, 0], [img_crop_width, img_crop_height], [0, img_crop_height]])
    M = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(img, M, (img_crop_width, img_crop_height), borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    if dst_img.shape[0] * 1.0 / dst_img.shape[1] >= 1.5: dst_img = np.rot90(dst_img)
    return dst_img

def sorted_boxes(dt_boxes):
    _boxes = list(sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0])))
    for i in range(len(_boxes) - 1):
        for j in range(i, -1, -1):
            if abs(_boxes[j+1][0][1] - _boxes[j][0][1]) < 10 and (_boxes[j+1][0][0] < _boxes[j][0][0]):
                _boxes[j], _boxes[j+1] = _boxes[j+1], _boxes[j]
            else: break
    return _boxes

def load_recognizer():
    config = Cfg.load_config_from_name('vgg_transformer')
    config['cnn']['pretrained'] = False 
    config['device'] = 'cpu'
    detector = Predictor(config)
    return detector

def remove_stroke_by_hsv(crop_img):
    # crop_img is BGR. Convert to HSV
    hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
    
    # Định nghĩa dải màu Vàng (Hue: 15-45, Saturation > 50, Value > 80)
    lower_yellow = np.array([15, 50, 80])
    upper_yellow = np.array([45, 255, 255])
    
    # Lọc mask: Các pixel trong dải màu Vàng sẽ thành Trắng (255), còn lại thành Đen (0)
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # Dilation nhẹ để làm nét chữ mập mạp, dễ đọc hơn (bù lại phần rìa vàng bị hòa vào đen)
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # VietOCR cần chữ màu Đen trên nền Trắng
    mask_inv = cv2.bitwise_not(mask)
    
    # Đưa về 3 kênh màu để tương thích code OCR
    clean_img = cv2.cvtColor(mask_inv, cv2.COLOR_GRAY2BGR)
    return clean_img

def process_image(img_path, output_dir, detector, recognizer):
    img = cv2.imread(img_path)
    if img is None: return
    dt_boxes = sorted_boxes(detector(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    
    name, ext = os.path.splitext(os.path.basename(img_path))
    full_text = []
    
    for idx, box in enumerate(dt_boxes):
        crop_img = get_rotate_crop_image(img, box)
        
        # Tiền xử lý HSV
        clean_crop_img = remove_stroke_by_hsv(crop_img)
        
        cv2.imwrite(os.path.join(output_dir, f"{name}_crop_{idx}_raw{ext}"), crop_img)
        cv2.imwrite(os.path.join(output_dir, f"{name}_crop_{idx}{ext}"), clean_crop_img)
        
        pil_img = Image.fromarray(cv2.cvtColor(clean_crop_img, cv2.COLOR_BGR2RGB))
        text = recognizer.predict(pil_img)
        full_text.append(text)
        
        with open(os.path.join(output_dir, f"{name}_crop_{idx}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
            
    with open(os.path.join(output_dir, f"{name}_full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))
    print(f"Processed {img_path}: saved {len(dt_boxes)} regions to {output_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output")
    parser.add_argument("--model_dir", default="onnx")
    args = parser.parse_args()
    if not os.path.exists(args.output): os.makedirs(args.output)
    
    detector = TextDetector(model_dir=args.model_dir)
    recognizer = load_recognizer()
    process_image(args.input, args.output, detector, recognizer)

if __name__ == "__main__":
    main()
