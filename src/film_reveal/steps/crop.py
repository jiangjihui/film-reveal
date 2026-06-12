"""
黑白胶卷翻拍后期处理 — 裁切步骤

包含 UI 组件创建、事件绑定和裁切相关回调函数。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import apply_crop_with_offsets, draw_crop_overlay
from film_reveal.processing.detection import auto_detect_crop_boundaries, detect_crop_on_rotated


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_crop_ui() -> dict:
    """创建裁切步骤的 UI 组件，返回组件引用字典。

    必须在 gr.Blocks() 上下文中调用。
    """
    components = {}

    gr.Markdown("### 🖊️ Step 1: 裁切")
    gr.Markdown(
        "> 自动检测胶卷片基边缘。每张图的裁切偏移量独立调整。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            components["auto_crop_btn"] = gr.Button("🔍 重新自动检测", variant="secondary")
            components["apply_crop_btn"] = gr.Button("✅ 应用裁切", variant="primary")
            components["crop_status"] = gr.Textbox(label="裁切状态", interactive=False)
        with gr.Column(scale=2):
            components["crop_preview"] = gr.Image(
                label="裁切预览（红色框 = 裁切边界，半透明区域 = 将被裁掉的部分）",
                type="pil",
            )

    with gr.Row():
        components["top_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label="上边距偏移（%）", info="正值向内收缩，负值向外扩展",
        )
        components["bottom_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label="下边距偏移（%）", info="正值向内收缩，负值向外扩展",
        )
        components["left_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label="左边距偏移（%）", info="正值向内收缩，负值向外扩展",
        )
        components["right_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label="右边距偏移（%）", info="正值向内收缩，负值向外扩展",
        )

    components["cropped_gallery"] = gr.Gallery(
        label="裁切结果", columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_crop_events(components: dict, state: AppState):
    """绑定裁切步骤的事件回调。

    Args:
        components: 裁切步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
    """
    top_slider = components["top_slider"]
    bottom_slider = components["bottom_slider"]
    left_slider = components["left_slider"]
    right_slider = components["right_slider"]

    # ── 偏移量滑块变化 ──
    def on_slider_change(top_offset, bottom_offset, left_offset, right_offset):
        """裁切滑块值变化时，更新当前选中图片的裁切参数并刷新预览。"""
        if not state.original_images or state.selected_index not in state.crop_params:
            return None

        idx = state.selected_index
        params = state.crop_params[idx]

        params["offsets"] = {
            "top": top_offset,
            "bottom": bottom_offset,
            "left": left_offset,
            "right": right_offset,
        }

        working_img = state.get_working_image(idx)
        preview = draw_crop_overlay(
            working_img,
            params["base_boundaries"],
            params["offsets"],
        )
        return preview

    for slider in [top_slider, bottom_slider, left_slider, right_slider]:
        slider.change(
            fn=on_slider_change,
            inputs=[top_slider, bottom_slider, left_slider, right_slider],
            outputs=components["crop_preview"],
        )

    # ── 自动检测裁切 ──
    def on_auto_crop():
        """重新对所有图片执行自动裁切检测，偏移量重置为 0。"""
        if not state.original_images:
            return None, 0, 0, 0, 0, "请先上传图片"

        for i in range(len(state.original_images)):
            working = state.get_working_image(i)
            original = state.original_images[i]
            boundaries = detect_crop_on_rotated(working, original)
            state.crop_params[i] = {
                "base_boundaries": boundaries,
                "offsets": {"top": 0, "bottom": 0, "left": 0, "right": 0},
            }

        idx = state.selected_index
        params = state.crop_params[idx]
        working_img = state.get_working_image(idx)
        preview = draw_crop_overlay(
            working_img,
            params["base_boundaries"],
            params["offsets"],
        )
        return preview, 0, 0, 0, 0, "裁切边界已重新检测，偏移量已重置"

    components["auto_crop_btn"].click(
        fn=on_auto_crop,
        outputs=[components["crop_preview"], top_slider, bottom_slider, left_slider, right_slider, components["crop_status"]],
    )

    # ── 应用裁切（批量） ──
    def on_apply_crop():
        """应用裁切：根据每张图的参数裁切所有图片。"""
        if not state.original_images:
            return [], None, "请先上传图片"

        state.cropped_images = []
        cropped_gallery = []

        for i in range(len(state.original_images)):
            working_img = state.get_working_image(i)
            params = state.crop_params[i]
            cropped = apply_crop_with_offsets(
                working_img, params["base_boundaries"], params["offsets"]
            )
            state.cropped_images.append(cropped)
            cropped_gallery.append((cropped, f"裁切后 #{i+1}"))

        state.clear_downstream("cropped")

        preview = state.cropped_images[state.selected_index]
        return cropped_gallery, preview, "裁切完成！可继续进行去色处理"

    components["apply_crop_btn"].click(
        fn=on_apply_crop,
        outputs=[components["cropped_gallery"], components["crop_preview"], components["crop_status"]],
    )