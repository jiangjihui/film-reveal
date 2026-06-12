"""
黑白胶卷翻拍后期处理 — 应用状态管理

包含 TypedDict 类型定义和 AppState 类。
AppState 不作为全局单例使用，由 app.py 创建并注入给各步骤模块。
"""

from typing import TypedDict
from PIL import Image


# ── 类型定义 ────────────────────────────────────────────────────────────

class RotationParams(TypedDict):
    """每张图片的旋转参数。"""
    base_angle: int       # 快速旋转基数（0/90/180/270）
    fine_angle: float     # 精细调整角度


class CropOffsets(TypedDict):
    """裁切偏移量（百分比）。正值向内收缩，负值向外扩展。"""
    top: int
    bottom: int
    left: int
    right: int


class CropParams(TypedDict):
    """每张图片的裁切参数。"""
    base_boundaries: dict[str, int]   # 自动检测的裁切边界
    offsets: CropOffsets               # 手动调整偏移


# ── 应用状态 ────────────────────────────────────────────────────────────

class AppState:
    """管理批量图片处理流水线的中间状态。"""

    def __init__(self):
        self.reset()

    def reset(self):
        """上传新图片时重置所有状态。"""
        self.original_images: list[Image.Image] = []
        self.rotated_images: list[Image.Image | None] = []
        self.cropped_images: list[Image.Image] = []
        self.desaturated_images: list[Image.Image] = []
        self.inverted_images: list[Image.Image] = []
        # 每张图独立的旋转参数：{索引: RotationParams}
        self.rotation_params: dict[int, RotationParams] = {}
        # 每张图独立的裁切参数：{索引: CropParams}
        self.crop_params: dict[int, CropParams] = {}
        self.selected_index: int = 0

    def get_working_image(self, idx: int) -> Image.Image:
        """获取指定索引的当前工作图片（已旋转则为旋转后图片，否则原图）。"""
        if idx < len(self.rotated_images) and self.rotated_images[idx] is not None:
            return self.rotated_images[idx]
        return self.original_images[idx]

    def get_total_rotation(self, idx: int) -> float:
        """获取指定索引的总旋转角度（base_angle + fine_angle）。"""
        if idx in self.rotation_params:
            return self.rotation_params[idx]["base_angle"] + self.rotation_params[idx]["fine_angle"]
        return 0.0

    def clear_downstream(self, from_step: str):
        """清除指定步骤之后的所有缓存。

        Args:
            from_step: 步骤名称，如 "rotated", "cropped", "desaturated"
                       该步骤之后的所有图片缓存将被清空
        """
        steps = ["rotated", "cropped", "desaturated", "inverted"]
        start = steps.index(from_step) + 1
        for step in steps[start:]:
            setattr(self, f"{step}_images", [])