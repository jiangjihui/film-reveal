"""
黑白胶卷翻拍后期处理 — 步骤共享辅助函数

统一批处理模式，消除各步骤回调中的重复迭代代码。
画廊标签只用简单编号（如 "#1"），因为每个画廊区块的标题已是翻译过的。
"""

from film_reveal.state import AppState
from PIL import Image


def make_thumbnail(img: Image.Image, max_size: int = 300) -> Image.Image:
    """生成缩略图，保持宽高比，最大边不超过 max_size。

    Args:
        img: 原始 PIL Image
        max_size: 缩略图最大边长（像素）

    Returns:
        缩略图 PIL Image（新对象，不修改原图）
    """
    thumb = img.copy()
    thumb.thumbnail((max_size, max_size))
    return thumb


def batch_process(
    state: AppState,
    source_list_name: str,
    process_fn,
    target_list_name: str,
    clear_downstream_from: str,
    thumbnail_size: int = 300,
) -> tuple[list[Image.Image], list[tuple]]:
    """
    统一的批处理迭代器，消除 4 个步骤回调中的重复代码。

    对所有图片依次执行处理，更新状态，清空下游缓存。

    Args:
        state: 应用状态实例
        source_list_name: 源图片列表名（如 "original_images", "rotated_images"）
        process_fn: 处理单张图片的函数，接收 PIL Image 返回 PIL Image
        target_list_name: 目标图片列表名（如 "rotated_images", "cropped_images"）
        clear_downstream_from: 清空下游缓存的起始步骤名（如 "rotated"）
        thumbnail_size: 缩略图最大边长（像素），默认 300

    Returns:
        tuple: (results 图片列表, gallery_tuples 画廊元组列表)
    """
    results = []
    gallery_tuples = []
    for i in range(len(state.original_images)):
        source_list = getattr(state, source_list_name)
        source_img = source_list[i] if i < len(source_list) else None
        if source_img is None:
            source_img = state.get_working_image(i)
        result = process_fn(source_img)
        results.append(result)
        gallery_tuples.append((make_thumbnail(result, thumbnail_size), "#" + str(i+1)))

    setattr(state, target_list_name, results)
    state.clear_downstream(clear_downstream_from)
    return results, gallery_tuples