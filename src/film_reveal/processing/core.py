"""
黑白胶卷翻拍后期处理 — 基础图像操作

纯函数模块，无 UI 依赖。
所有函数接收 PIL Image 输入、返回 PIL Image。
"""

import numpy as np
from PIL import Image, ImageDraw


# ── 偏移量计算辅助 ────────────────────────────────────────────────────

def _apply_offsets(
    boundaries: dict, offsets: dict, width: int, height: int
) -> dict:
    """
    在基础裁切边界上叠加百分比偏移量，返回调整后的边界。

    偏移量为百分比，正值向内收缩（裁切更多），负值向外扩展（保留更多）。
    消除 apply_crop_with_offsets 和 draw_crop_overlay 中的重复计算。

    Args:
        boundaries: 基础裁切边界 {"top", "bottom", "left", "right"}
        offsets: 手动偏移量（%） {"top", "bottom", "left", "right"}
        width: 图片宽度
        height: 图片高度

    Returns:
        dict: 调整后的裁切边界，如果偏移过大导致无效区域则回退到基础边界
    """
    adjusted = {
        "top": max(0, boundaries["top"] + int(height * offsets["top"] / 100)),
        "bottom": min(height, boundaries["bottom"] - int(height * offsets["bottom"] / 100)),
        "left": max(0, boundaries["left"] + int(width * offsets["left"] / 100)),
        "right": min(width, boundaries["right"] - int(width * offsets["right"] / 100)),
    }
    # 确保裁切区域有效
    if adjusted["right"] <= adjusted["left"] or adjusted["bottom"] <= adjusted["top"]:
        adjusted = boundaries
    return adjusted


# ── 旋转 ────────────────────────────────────────────────────────────

def rotate_image(img: Image.Image, angle: float) -> Image.Image:
    """
    旋转图片，使用 PIL Image.rotate 并自动扩展画布以避免裁切丢失内容。

    背景填充为白色，与片基颜色一致。

    Args:
        img: PIL Image
        angle: 旋转角度（度），正值逆时针旋转

    Returns:
        PIL Image: 旋转后的图片
    """
    return img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))


# ── 裁切 ────────────────────────────────────────────────────────────

def apply_crop(img: Image.Image, boundaries: dict) -> Image.Image:
    """
    根据裁切边界裁切图片。

    Args:
        img: PIL Image
        boundaries: {"top": int, "bottom": int, "left": int, "right": int}

    Returns:
        PIL Image: 裁切后的图片
    """
    return img.crop((
        boundaries["left"],
        boundaries["top"],
        boundaries["right"],
        boundaries["bottom"],
    ))


def apply_crop_with_offsets(img: Image.Image, base_boundaries: dict, offsets: dict) -> Image.Image:
    """
    在基础裁切边界上叠加手动偏移量后裁切。

    偏移量为百分比，正值向内收缩（裁切更多），负值向外扩展（保留更多）。

    Args:
        img: PIL Image
        base_boundaries: 自动检测的基础边界
        offsets: {"top": int, "bottom": int, "left": int, "right": int}
                 手动偏移量（%），正值向内，负值向外

    Returns:
        PIL Image: 裁切后的图片
    """
    width, height = img.size
    adjusted = _apply_offsets(base_boundaries, offsets, width, height)
    return apply_crop(img, adjusted)


def draw_crop_overlay(img: Image.Image, boundaries: dict, offsets: dict = None) -> Image.Image:
    """
    在图片上绘制半透明红色裁切遮罩和红色边框。

    被裁切掉的区域（框外）覆盖半透明红色遮罩（alpha=100/255 ≈ 40%透明度），
    用户可以透过遮罩看到原图细节，方便判断裁切边界是否贴合。

    Args:
        img: PIL Image（原图）
        boundaries: 基础裁切边界
        offsets: 手动偏移量（可选，默认全为 0）

    Returns:
        PIL Image: 带半透明遮罩和边框的预览图（RGB 格式）
    """
    if offsets is None:
        offsets = {"top": 0, "bottom": 0, "left": 0, "right": 0}

    width, height = img.size
    adjusted = _apply_offsets(boundaries, offsets, width, height)

    # 原图转为 RGBA，以便叠加半透明遮罩
    preview = img.copy().convert("RGBA")

    # 创建半透明红色遮罩层
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # 被裁掉区域的半透明红色遮罩 (alpha=100 ≈ 40% 透明度)
    mask_color = (200, 0, 0, 100)

    if adjusted["top"] > 0:
        overlay_draw.rectangle([0, 0, width - 1, adjusted["top"] - 1], fill=mask_color)
    if adjusted["bottom"] < height:
        overlay_draw.rectangle([0, adjusted["bottom"], width - 1, height - 1], fill=mask_color)
    if adjusted["left"] > 0:
        overlay_draw.rectangle([0, adjusted["top"], adjusted["left"] - 1, adjusted["bottom"] - 1], fill=mask_color)
    if adjusted["right"] < width:
        overlay_draw.rectangle([adjusted["right"], adjusted["top"], width - 1, adjusted["bottom"] - 1], fill=mask_color)

    # 将遮罩层合成到原图上
    preview = Image.alpha_composite(preview, overlay)

    # 在合成后的图上绘制裁切边框（3px 红色实线）
    border_draw = ImageDraw.Draw(preview)
    box = [adjusted["left"], adjusted["top"], adjusted["right"] - 1, adjusted["bottom"] - 1]
    border_color = (255, 0, 0, 255)  # 纯红色，完全不透明
    for i in range(3):
        expanded_box = [box[0] - i, box[1] - i, box[2] + i, box[3] + i]
        border_draw.rectangle(expanded_box, outline=border_color)

    # 转回 RGB 以兼容 Gradio Image 组件
    return preview.convert("RGB")


# ── 去色 ────────────────────────────────────────────────────────────

def desaturate(img: Image.Image) -> Image.Image:
    """
    去色：将 RGB 图片转为单通道灰度图。

    手机翻拍产生的 RGB 色彩信息（偏色、色温干扰）是干扰源，
    需要去除还原为黑白。

    Args:
        img: PIL Image

    Returns:
        PIL Image: 灰度图（mode="L"），转为 RGB 以兼容 Gradio 显示
    """
    gray = img.convert("L")
    return gray.convert("RGB")  # Gradio Image 组件需要 RGB 格式


# ── 反转 ────────────────────────────────────────────────────────────

def invert(img: Image.Image) -> Image.Image:
    """
    反转：将黑白负片转为正片。

    负片中暗区 → 正片中亮区（还原真实明暗关系）。
    使用 NumPy 255 - arr 实现。

    Args:
        img: PIL Image

    Returns:
        PIL Image: 反转后的图片
    """
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb)
    inverted_arr = 255 - arr
    return Image.fromarray(inverted_arr)