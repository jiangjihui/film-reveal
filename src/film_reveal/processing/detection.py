"""
黑白胶卷翻拍后期处理 — 自动检测算法

纯函数模块，无 UI 依赖。
包含倾斜检测、裁切边界检测，以及旋转后图片的裁切检测。
"""

import numpy as np
from PIL import Image

from .core import apply_crop


# ── 倾斜检测 ────────────────────────────────────────────────────────────

def auto_detect_tilt_angle(img: Image.Image) -> float:
    """
    自动检测翻拍负片的倾斜角度。

    算法原理：分块均值法
    把图片切成若干条带，每个条带单独计算行均值（压平了内容内部的明暗波动），
    用梯度法在每个条带中找到片基边界的行号，多个条带的边界行号连起来就是
    片基边界线的真实走向，线性回归拟合出斜率 → 倾斜角度。

    旋转方向约定：PIL rotate(angle) 正值 = 逆时针。
    如果片基上边界右侧行号更大（图片右端偏下/右倾），需逆时针矫正 → 正角度。

    性能优化：先在缩小后的图片上检测，角度与缩放无关。

    Args:
        img: PIL Image，翻拍的胶卷负片照片

    Returns:
        float: 建议的旋转角度（度），正值逆时针矫正
               如果检测不到明显倾斜，返回 0.0
    """
    # 缩小图片以加速检测，最大边 1000px
    max_side = 1000
    orig_w, orig_h = img.size
    largest_side = max(orig_w, orig_h)
    if largest_side > max_side:
        scale = max_side / largest_side
        small_w = int(orig_w * scale)
        small_h = int(orig_h * scale)
        small_img = img.resize((small_w, small_h), Image.LANCZOS)
    else:
        small_img = img

    boundaries = auto_detect_crop_boundaries(small_img)

    width, height = small_img.size
    top, bottom = boundaries["top"], boundaries["bottom"]
    left, right = boundaries["left"], boundaries["right"]

    has_top_base = top > 5
    has_bottom_base = (height - bottom) > 5
    has_left_base = left > 5
    has_right_base = (width - right) > 5

    if not (has_top_base or has_bottom_base or has_left_base or has_right_base):
        return 0.0

    gray = small_img.convert("L")
    arr = np.array(gray, dtype=float)

    NUM_STRIPS = 6

    # ── 水平边界（上/下）：纵向条带 ──
    top_boundary_points = []
    bottom_boundary_points = []

    if has_top_base or has_bottom_base:
        strip_width = width // NUM_STRIPS
        for s in range(NUM_STRIPS):
            x_start = s * strip_width
            x_end = min((s + 1) * strip_width, width)
            strip_center_x = (x_start + x_end) / 2

            strip_arr = arr[:, x_start:x_end]
            row_means = strip_arr.mean(axis=1)
            row_diff = np.diff(row_means)

            # 上边界
            if has_top_base:
                search_end = min(len(row_diff), height // 2)
                segment = row_diff[:search_end]
                scores = -segment
                abs_median = np.median(np.abs(segment))
                min_sig = max(abs_median * 3, 5)
                significant = scores > min_sig
                if np.any(significant):
                    best_idx = np.where(significant)[0][np.argmax(scores[significant])]
                    top_boundary_points.append((strip_center_x, float(best_idx + 1)))

            # 下边界
            if has_bottom_base:
                search_start = max(0, height // 2)
                segment = row_diff[search_start:]
                scores = segment
                abs_median = np.median(np.abs(segment))
                min_sig = max(abs_median * 3, 5)
                significant = scores > min_sig
                if np.any(significant):
                    best_idx = np.where(significant)[0][np.argmax(scores[significant])]
                    row_y = search_start + best_idx + 1
                    bottom_boundary_points.append((strip_center_x, float(row_y)))

    # ── 垂直边界（左/右）：横向条带 ──
    left_boundary_points = []
    right_boundary_points = []

    if has_left_base or has_right_base:
        strip_height = height // NUM_STRIPS
        for s in range(NUM_STRIPS):
            y_start = s * strip_height
            y_end = min((s + 1) * strip_height, height)
            strip_center_y = (y_start + y_end) / 2

            strip_arr = arr[y_start:y_end, :]
            col_means = strip_arr.mean(axis=0)
            col_diff = np.diff(col_means)

            # 左边界
            if has_left_base:
                search_end = min(len(col_diff), width // 2)
                segment = col_diff[:search_end]
                scores = -segment
                abs_median = np.median(np.abs(segment))
                min_sig = max(abs_median * 3, 5)
                significant = scores > min_sig
                if np.any(significant):
                    best_idx = np.where(significant)[0][np.argmax(scores[significant])]
                    left_boundary_points.append((float(best_idx + 1), strip_center_y))

            # 右边界
            if has_right_base:
                search_start = max(0, width // 2)
                segment = col_diff[search_start:]
                scores = segment
                abs_median = np.median(np.abs(segment))
                min_sig = max(abs_median * 3, 5)
                significant = scores > min_sig
                if np.any(significant):
                    best_idx = np.where(significant)[0][np.argmax(scores[significant])]
                    col_x = search_start + best_idx + 1
                    right_boundary_points.append((float(col_x), strip_center_y))

    # ── 为每条边界线分别拟合斜率，选择最可靠的一条 ──
    def fit_line(points):
        """对一组点做线性回归，返回 (slope, num_points) 或 None。"""
        if len(points) < 3:
            return None
        x_coords = np.array([p[0] for p in points])
        y_coords = np.array([p[1] for p in points])
        A = np.vstack([x_coords, np.ones(len(x_coords))]).T
        result = np.linalg.lstsq(A, y_coords, rcond=None)
        return (result[0][0], len(points))

    all_fits = []
    for points in [top_boundary_points, bottom_boundary_points, left_boundary_points, right_boundary_points]:
        fit = fit_line(points)
        if fit is not None:
            all_fits.append(fit)

    if not all_fits:
        return 0.0

    # 选择点数最多的那条边界线的斜率（最可靠）
    best_fit = max(all_fits, key=lambda f: f[1])
    slope = best_fit[0]

    angle_deg = np.degrees(np.arctan(slope))
    angle_deg = max(-45, min(45, angle_deg))

    if abs(angle_deg) < 0.5:
        return 0.0

    return round(angle_deg * 2) / 2


# ── 裁切边界检测 ────────────────────────────────────────────────────────

def auto_detect_crop_boundaries(img: Image.Image) -> dict:
    """
    自动检测胶卷片基边缘，返回裁切边界。

    翻拍黑白胶卷负片时，片基（胶卷外边缘）在照片中表现为亮/白色区域，
    与实际图像内容的暗区有明显的亮度差异。

    检测策略：
    1. 先将图片缩小到最大边 1000px，加速计算（坐标最后映射回原图）
    2. 转灰度，计算每行/列的平均亮度曲线
    3. 对亮度曲线取一阶差分（梯度），找到亮度骤降的转折点
    4. 从四个边缘向内扫描，找梯度绝对值最大的点作为裁切边界

    这种梯度法比阈值法更鲁棒：不依赖固定阈值，而是找亮度变化最剧烈的位置，
    即使片基区域不特别亮、图像内容不特别暗也能正确检测。

    Args:
        img: PIL Image，翻拍的胶卷负片照片

    Returns:
        dict: {"top": int, "bottom": int, "left": int, "right": int}
              值为像素坐标，可直接用于 PIL Image.crop()
    """
    # 缩小图片以加速检测，最大边 1000px
    max_side = 1000
    orig_w, orig_h = img.size
    largest_side = max(orig_w, orig_h)
    if largest_side > max_side:
        scale = max_side / largest_side
        small_w = int(orig_w * scale)
        small_h = int(orig_h * scale)
        small_img = img.resize((small_w, small_h), Image.LANCZOS)
    else:
        scale = 1.0
        small_img = img

    gray = small_img.convert("L")
    arr = np.array(gray)
    height, width = arr.shape

    row_means = arr.mean(axis=1)
    col_means = arr.mean(axis=0)

    row_diff = np.diff(row_means)
    col_diff = np.diff(col_means)

    top = _find_edge_from_start(row_diff, direction="negative", max_search=height // 2)
    bottom = _find_edge_from_end(row_diff, total_length=height, direction="positive", max_search=height // 2)
    left = _find_edge_from_start(col_diff, direction="negative", max_search=width // 2)
    right = _find_edge_from_end(col_diff, total_length=width, direction="positive", max_search=width // 2)

    # 如果梯度法没有找到明显边界，回退到阈值法
    fallback_threshold = arr.mean()
    if top == 0 and row_means[0] > fallback_threshold:
        for i in range(height):
            if row_means[i] < fallback_threshold:
                top = i
                break
    if bottom == height and row_means[-1] > fallback_threshold:
        for i in range(height - 1, -1, -1):
            if row_means[i] < fallback_threshold:
                bottom = i + 1
                break
    if left == 0 and col_means[0] > fallback_threshold:
        for j in range(width):
            if col_means[j] < fallback_threshold:
                left = j
                break
    if right == width and col_means[-1] > fallback_threshold:
        for j in range(width - 1, -1, -1):
            if col_means[j] < fallback_threshold:
                right = j + 1
                break

    # 安全检查：确保裁切区域不会太小（至少保留 10% 的面积）
    crop_area = (right - left) * (bottom - top)
    total_area = width * height
    if crop_area < total_area * 0.1:
        return {"top": 0, "bottom": orig_h, "left": 0, "right": orig_w}

    # 将坐标映射回原图尺寸
    inv_scale = 1.0 / scale
    return {
        "top": int(top * inv_scale),
        "bottom": int(bottom * inv_scale),
        "left": int(left * inv_scale),
        "right": int(right * inv_scale),
    }


def detect_crop_on_rotated(img: Image.Image, original_img: Image.Image) -> dict:
    """
    对旋转后的图片检测裁切边界，自动处理旋转扩展的白色边框。

    如果图片被旋转过（尺寸比原图大），先裁掉旋转扩展的白色边框，
    再在原图内容区域内检测片基边界，最后映射回扩展画布坐标。

    纯函数版本，从 _crop_detect_on_working_image 重构而来，
    不依赖 state，只接收图片参数。

    Args:
        img: 当前工作图片（可能经过旋转扩展）
        original_img: 原始图片（用于尺寸比较）

    Returns:
        dict: {"top": int, "bottom": int, "left": int, "right": int}
              裁切边界坐标（相对于工作图片）
    """
    # 如果工作图片和原图尺寸相同（未旋转或 180° 旋转），直接检测
    if img.size == original_img.size:
        return auto_detect_crop_boundaries(img)

    # 图片尺寸不同 = 旋转后扩展了画布，需要剥离扩展边框
    orig_w, orig_h = original_img.size
    work_w, work_h = img.size

    # 计算扩展边框的大致宽度
    margin_x = max(5, (work_w - orig_w) // 2 + 5)
    margin_y = max(5, (work_h - orig_h) // 2 + 5)

    # 先裁掉边框区域，只保留内部原图内容
    inner_img = apply_crop(img, {
        "top": margin_y, "bottom": work_h - margin_y,
        "left": margin_x, "right": work_w - margin_x,
    })

    # 在内部区域检测裁切边界
    inner_boundaries = auto_detect_crop_boundaries(inner_img)

    # 映射回扩展画布全图坐标
    return {
        "top": margin_y + inner_boundaries["top"],
        "bottom": margin_y + inner_boundaries["bottom"],
        "left": margin_x + inner_boundaries["left"],
        "right": margin_x + inner_boundaries["right"],
    }


# ── 内部辅助函数 ────────────────────────────────────────────────────────

def _find_edge_from_start(diff_array: np.ndarray, direction: str, max_search: int) -> int:
    """
    从差分数组起始端扫描，找到梯度绝对值最大的位置。

    Args:
        diff_array: 一阶差分数组
        direction: "negative" 找最大负梯度（亮度骤降），"positive" 找最大正梯度（亮度骤升）
        max_search: 最大搜索范围（像素数）

    Returns:
        int: 边界位置索引
    """
    search_len = min(len(diff_array), max_search)
    if search_len == 0:
        return 0

    segment = diff_array[:search_len]

    if direction == "negative":
        scores = -segment
    else:
        scores = segment

    abs_median = np.median(np.abs(segment))
    min_significance = max(abs_median * 3, 5)

    significant_mask = scores > min_significance
    if not np.any(significant_mask):
        return 0

    significant_indices = np.where(significant_mask)[0]
    best_idx = significant_indices[np.argmax(scores[significant_indices])]
    return best_idx + 1


def _find_edge_from_end(diff_array: np.ndarray, total_length: int, direction: str, max_search: int) -> int:
    """
    从差分数组末尾端扫描，找到梯度绝对值最大的位置。

    Args:
        diff_array: 一阶差分数组
        total_length: 原始数组长度
        direction: "negative" 找最大负梯度，"positive" 找最大正梯度
        max_search: 最大搜索范围（像素数）

    Returns:
        int: 边界位置索引（原始数组中的索引）
    """
    search_len = min(len(diff_array), max_search)
    if search_len == 0:
        return total_length

    segment = diff_array[-search_len:]

    if direction == "positive":
        scores = segment
    else:
        scores = -segment

    abs_median = np.median(np.abs(segment))
    min_significance = max(abs_median * 3, 5)

    significant_mask = scores > min_significance
    if not np.any(significant_mask):
        return total_length

    significant_indices = np.where(significant_mask)[0]
    best_idx = significant_indices[np.argmax(scores[significant_indices])]
    original_idx = (total_length - search_len) + best_idx + 1
    return original_idx