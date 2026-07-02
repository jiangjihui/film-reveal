"""
黑白胶卷翻拍后期处理 — 裁切步骤

包含 UI 组件创建、事件绑定和裁切相关回调函数。
使用 Gradio I18n 实现多语言支持。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import apply_crop_with_offsets, draw_crop_overlay
from film_reveal.processing.detection import auto_detect_crop_boundaries, detect_crop_on_rotated
from film_reveal.steps.common import make_thumbnail


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_crop_ui(i18n) -> dict:
    """创建裁切步骤的 UI 组件，返回组件引用字典。

    Args:
        i18n: Gradio I18n 实例，用于多语言翻译
    """
    components = {}

    gr.Markdown(i18n("crop_section"))
    gr.Markdown(i18n("crop_description"))

    with gr.Row():
        with gr.Column(scale=1):
            components["auto_crop_btn"] = gr.Button(i18n("auto_crop_btn"), variant="secondary")
            components["no_crop_btn"] = gr.Button(i18n("no_crop_btn"), variant="secondary")
            components["apply_crop_btn"] = gr.Button(i18n("apply_crop_btn"), variant="primary")
            components["crop_status"] = gr.Textbox(label=i18n("crop_status_label"), interactive=False)
        with gr.Column(scale=2):
            components["crop_preview"] = gr.Image(
                label=i18n("crop_preview_label"),
                type="pil",
            )

    with gr.Row():
        components["top_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label=i18n("top_slider_label"), info=i18n("slider_info"),
        )
        components["bottom_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label=i18n("bottom_slider_label"), info=i18n("slider_info"),
        )
        components["left_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label=i18n("left_slider_label"), info=i18n("slider_info"),
        )
        components["right_slider"] = gr.Slider(
            minimum=-30, maximum=30, value=0, step=1,
            label=i18n("right_slider_label"), info=i18n("slider_info"),
        )

    components["cropped_gallery"] = gr.Gallery(
        label=i18n("cropped_gallery_label"), columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_crop_events(components: dict, state: AppState, i18n):
    """绑定裁切步骤的事件回调。

    Args:
        components: 裁切步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
        i18n: Gradio I18n 实例（通过闭包注入）
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
            return None, 0, 0, 0, 0, i18n("msg_upload_first")

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
        return preview, 0, 0, 0, 0, i18n("msg_crop_redetected")

    components["auto_crop_btn"].click(
        fn=on_auto_crop,
        outputs=[components["crop_preview"], top_slider, bottom_slider, left_slider, right_slider, components["crop_status"]],
    )

    # ── 不裁切 ──
    def on_no_crop():
        """对所有图片设置不裁切（保留完整图片）。"""
        if not state.original_images:
            return None, 0, 0, 0, 0, i18n("msg_upload_first")

        for i in range(len(state.original_images)):
            working_img = state.get_working_image(i)
            width, height = working_img.size
            state.crop_params[i] = {
                "base_boundaries": {"top": 0, "bottom": height, "left": 0, "right": width},
                "offsets": {"top": 0, "bottom": 0, "left": 0, "right": 0},
            }

        idx = state.selected_index
        working_img = state.get_working_image(idx)
        preview = draw_crop_overlay(
            working_img,
            state.crop_params[idx]["base_boundaries"],
            state.crop_params[idx]["offsets"],
        )
        return preview, 0, 0, 0, 0, i18n("msg_no_crop")

    components["no_crop_btn"].click(
        fn=on_no_crop,
        outputs=[components["crop_preview"], top_slider, bottom_slider, left_slider, right_slider, components["crop_status"]],
    )

    # ── 应用裁切（批量） ──
    def on_apply_crop():
        """应用裁切：根据每张图的参数裁切所有图片。"""
        if not state.original_images:
            return [], None, i18n("msg_upload_first")

        state.cropped_images = []
        cropped_gallery = []

        for i in range(len(state.original_images)):
            working_img = state.get_working_image(i)
            params = state.crop_params[i]
            cropped = apply_crop_with_offsets(
                working_img, params["base_boundaries"], params["offsets"]
            )
            state.cropped_images.append(cropped)
            cropped_gallery.append((make_thumbnail(cropped), "#" + str(i+1)))

        state.clear_downstream("cropped")

        preview = state.cropped_images[state.selected_index]
        return cropped_gallery, preview, i18n("msg_crop_complete")

    components["apply_crop_btn"].click(
        fn=on_apply_crop,
        outputs=[components["cropped_gallery"], components["crop_preview"], components["crop_status"]],
    )