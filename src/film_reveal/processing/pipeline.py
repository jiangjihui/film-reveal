"""
黑白胶卷翻拍后期处理 — 处理管道组合逻辑

将各步骤组合为完整处理流程。
"""

from PIL import Image

from .core import rotate_image, apply_crop_with_offsets, desaturate, invert
from .detection import auto_detect_crop_boundaries


def process_pipeline(img: Image.Image, rotation_angle: float = 0.0, offsets: dict = None) -> dict:
    """
    一键完成全部处理步骤：旋转 → 自动裁切 → 去色 → 反转。

    Args:
        img: PIL Image（原图）
        rotation_angle: 旋转角度（度），默认 0
        offsets: 裁切偏移量（可选，默认全为 0，即纯自动检测）

    Returns:
        dict: {
            "original": PIL Image,
            "rotated": PIL Image,
            "cropped": PIL Image,
            "desaturated": PIL Image,
            "inverted": PIL Image,
            "boundaries": dict,
        }
    """
    if offsets is None:
        offsets = {"top": 0, "bottom": 0, "left": 0, "right": 0}

    rotated = rotate_image(img, rotation_angle) if rotation_angle != 0.0 else img
    boundaries = auto_detect_crop_boundaries(rotated)
    cropped = apply_crop_with_offsets(rotated, boundaries, offsets)
    desaturated_img = desaturate(cropped)
    inverted_result = invert(desaturated_img)

    return {
        "original": img,
        "rotated": rotated,
        "cropped": cropped,
        "desaturated": desaturated_img,
        "inverted": inverted_result,
        "boundaries": boundaries,
    }