"""
黑白胶卷翻拍后期处理 — 包入口
"""

from .core import (
    rotate_image,
    apply_crop,
    apply_crop_with_offsets,
    draw_crop_overlay,
    desaturate,
    invert,
)
from .detection import (
    auto_detect_tilt_angle,
    auto_detect_crop_boundaries,
    detect_crop_on_rotated,
)
from .pipeline import process_pipeline