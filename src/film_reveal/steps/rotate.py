"""
黑白胶卷翻拍后期处理 — 旋转步骤

包含 UI 组件创建、事件绑定和旋转相关回调函数。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import rotate_image
from film_reveal.processing.detection import auto_detect_tilt_angle


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_rotate_ui() -> dict:
    """创建旋转步骤的 UI 组件，返回组件引用字典。

    必须在 gr.Blocks() 上下文中调用。
    """
    components = {}

    gr.Markdown("### 🔄 Step 0: 旋转")
    gr.Markdown(
        "> 自动检测倾斜角度并矫正。快捷按钮调整大方向，微调滑块纠正细微倾斜。"
        "点击原图 Gallery 中的缩略图可切换选中，每张图独立调整。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            components["auto_tilt_btn"] = gr.Button("🔍 自动矫正倾斜", variant="secondary")
            components["apply_rotation_btn"] = gr.Button("✅ 应用旋转", variant="primary")
            components["rotation_status"] = gr.Textbox(label="旋转状态", interactive=False)
        with gr.Column(scale=2):
            components["rotation_preview"] = gr.Image(label="旋转预览", type="pil")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("**快捷方向按钮**")
            with gr.Row():
                components["rotate_0_btn"] = gr.Button("0°", variant="secondary")
                components["rotate_90_btn"] = gr.Button("90°", variant="secondary")
                components["rotate_180_btn"] = gr.Button("180°", variant="secondary")
                components["rotate_270_btn"] = gr.Button("270°", variant="secondary")
            components["rotation_base_display"] = gr.Number(
                label="当前基础方向（°）", value=0, interactive=False
            )
        with gr.Column(scale=1):
            components["rotation_slider"] = gr.Slider(
                minimum=-45, maximum=45, value=0, step=0.5,
                label="微调角度（°）",
                info="在基础方向上微调倾斜，正值逆时针，负值顺时针",
            )

    components["rotated_gallery"] = gr.Gallery(
        label="旋转结果", columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_rotate_events(components: dict, state: AppState, other_components: dict):
    """绑定旋转步骤的事件回调。

    Args:
        components: 旋转步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
        other_components: 其他步骤需要交互的组件（如 crop_preview）
    """
    crop_preview = other_components.get("crop_preview")

    def _ensure_rotated_list_len(state, idx):
        """确保 rotated_images 列表至少有 idx+1 个元素。"""
        while len(state.rotated_images) <= idx:
            state.rotated_images.append(None)

    # ── 自动检测倾斜 ──
    def on_auto_detect_tilt():
        """自动检测倾斜角度并填入滑块。不更新裁切边界。"""
        if not state.original_images:
            return None, 0.0, "请先上传图片"

        idx = state.selected_index
        detected_angle = auto_detect_tilt_angle(state.original_images[idx])
        state.rotation_params[idx]["fine_angle"] = detected_angle

        total_angle = state.get_total_rotation(idx)
        original = state.original_images[idx]
        rotated = rotate_image(original, total_angle) if total_angle != 0 else original
        _ensure_rotated_list_len(state, idx)
        state.rotated_images[idx] = rotated

        return rotated, detected_angle, f"检测到倾斜角度: {detected_angle}°（已自动填入微调滑块）"

    components["auto_tilt_btn"].click(
        fn=on_auto_detect_tilt,
        outputs=[components["rotation_preview"], components["rotation_slider"], components["rotation_status"]],
    )

    # ── 微调滑块变化 ──
    def on_rotation_slider_change(fine_angle):
        """旋转微调滑块变化时，只更新旋转预览。"""
        if not state.original_images or state.selected_index not in state.rotation_params:
            return None

        idx = state.selected_index
        state.rotation_params[idx]["fine_angle"] = fine_angle

        total_angle = state.get_total_rotation(idx)
        img = state.original_images[idx]
        rotated = rotate_image(img, total_angle) if total_angle != 0 else img
        _ensure_rotated_list_len(state, idx)
        state.rotated_images[idx] = rotated

        return rotated

    components["rotation_slider"].change(
        fn=on_rotation_slider_change,
        inputs=components["rotation_slider"],
        outputs=components["rotation_preview"],
    )

    # ── 快捷方向按钮 ──
    def on_quick_rotate(base_angle):
        """快捷方向按钮：设置基础旋转角度，重置微调滑块为 0。"""
        if not state.original_images:
            return None, 0.0, "请先上传图片"

        idx = state.selected_index
        state.rotation_params[idx]["base_angle"] = base_angle
        state.rotation_params[idx]["fine_angle"] = 0.0

        img = state.original_images[idx]
        rotated = rotate_image(img, base_angle) if base_angle != 0 else img
        _ensure_rotated_list_len(state, idx)
        state.rotated_images[idx] = rotated

        return rotated, 0.0, f"已旋转 {base_angle}°，微调滑块已重置为 0°"

    components["rotate_0_btn"].click(fn=lambda: on_quick_rotate(0), outputs=[components["rotation_preview"], components["rotation_slider"], components["rotation_status"]])
    components["rotate_90_btn"].click(fn=lambda: on_quick_rotate(90), outputs=[components["rotation_preview"], components["rotation_slider"], components["rotation_status"]])
    components["rotate_180_btn"].click(fn=lambda: on_quick_rotate(180), outputs=[components["rotation_preview"], components["rotation_slider"], components["rotation_status"]])
    components["rotate_270_btn"].click(fn=lambda: on_quick_rotate(270), outputs=[components["rotation_preview"], components["rotation_slider"], components["rotation_status"]])

    # ── 应用旋转（批量） ──
    def on_apply_rotation():
        """应用旋转：对所有图片执行旋转。"""
        if not state.original_images:
            return [], None, "请先上传图片"

        # 确保列表长度与原图一致
        state.rotated_images = [None] * len(state.original_images)
        rotated_gallery = []
        for i, img in enumerate(state.original_images):
            total_angle = state.get_total_rotation(i)
            rotated = rotate_image(img, total_angle) if total_angle != 0 else img
            state.rotated_images[i] = rotated
            rotated_gallery.append((rotated, f"旋转后 #{i+1}"))

        state.clear_downstream("rotated")

        preview = state.rotated_images[state.selected_index]
        return rotated_gallery, preview, "旋转完成！可继续进行裁切处理"

    components["apply_rotation_btn"].click(
        fn=on_apply_rotation,
        outputs=[components["rotated_gallery"], components["rotation_preview"], components["rotation_status"]],
    )