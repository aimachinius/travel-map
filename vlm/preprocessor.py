"""
Module preprocessor: Tiền xử lý ảnh độ phân giải động (Dynamic Resolution) theo chuẩn InternVL2 / Vintern-1B.
"""

from typing import List, Tuple
from PIL import Image

try:
    import torchvision.transforms as T
    from torchvision.transforms.functional import InterpolationMode
    TORCHVISION_AVAILABLE = True
except Exception:
    TORCHVISION_AVAILABLE = False
    T = None
    InterpolationMode = None



IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size: int = 448):
    """
    Transform chuẩn hóa ảnh về Tensor theo chuẩn ImageNet.
    """
    if not TORCHVISION_AVAILABLE:
        raise ImportError("torchvision chưa được cài đặt hoặc không khả dụng trên môi trường hiện tại.")

    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def find_closest_aspect_ratio(
    aspect_ratio: float,
    target_ratios: List[Tuple[int, int]],
    width: int,
    height: int,
    image_size: int
) -> Tuple[int, int]:
    """
    Tìm tỷ lệ khung hình mục tiêu tối ưu để bảo toàn tỷ lệ gốc mà không làm méo hình.
    """
    best_ratio_diff = float("inf")
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def dynamic_preprocess(
    image: Image.Image,
    min_num: int = 1,
    max_num: int = 4,
    image_size: int = 448,
    use_thumbnail: bool = True
) -> List[Image.Image]:
    """
    Chia khung hình thành các patch nhỏ 448x448 để bảo toàn độ nét chữ nhỏ OCR trên biển hiệu.
    """
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1)
        for i in range(1, n + 1) for j in range(1, n + 1)
        if i * j <= max_num and i * j >= min_num
    )
    sorted_target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, sorted_target_ratios, orig_width, orig_height, image_size
    )

    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    resize_img = image.resize((target_width, target_height), Image.Resampling.BICUBIC)
    processed_images = []
    for i in range(blocks):
        box = (
            (i % target_aspect_ratio[0]) * image_size,
            (i // target_aspect_ratio[0]) * image_size,
            ((i % target_aspect_ratio[0]) + 1) * image_size,
            ((i // target_aspect_ratio[0]) + 1) * image_size,
        )
        split_img = resize_img.crop(box)
        processed_images.append(split_img)

    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size), Image.Resampling.BICUBIC)
        processed_images.append(thumbnail_img)

    return processed_images
