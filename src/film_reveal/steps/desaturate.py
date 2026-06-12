"""
黑白胶卷翻拍后期处理 — 去色步骤

包含 UI 组件创建、事件绑定和去色回调函数。
使用 Gradio I18n 实现多语言支持。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import desaturate
from film_reveal.steps.common import batch_process


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_desaturate_ui(i18n) -> dict:
    """创建去色步骤的 UI 组件，返回组件引用字典。

    Args:
        i18n: Gradio I18n 实例，用于多语言翻译
    """
    components = {}

    gr.Markdown(i18n("desaturate_section"))
    gr.Markdown(i18n("desaturate_description"))

    with gr.Row():
        with gr.Column(scale=1):
            components["desaturate_btn"] = gr.Button(i18n("desaturate_btn"), variant="primary")
            components["desaturate_status"] = gr.Textbox(label=i18n("desaturate_status_label"), interactive=False)
        with gr.Column(scale=2):
            components["desaturate_preview"] = gr.Image(label=i18n("desaturate_preview_label"), type="pil")

    components["desaturated_gallery"] = gr.Gallery(
        label=i18n("desaturated_gallery_label"), columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_desaturate_events(components: dict, state: AppState, i18n):
    """绑定去色步骤的事件回调。

    Args:
        components: 去色步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
        i18n: Gradio I18n 实例（通过闭包注入）
    """
    def on_desaturate():
        """对所有裁切后图片执行去色处理。"""
        if not state.cropped_images:
            return [], None, i18n("msg_desaturate_first")

        results, gallery_tuples = batch_process(
            state,
            source_list_name="cropped_images",
            process_fn=desaturate,
            target_list_name="desaturated_images",
            clear_downstream_from="desaturated",
        )

        preview = results[state.selected_index]
        return gallery_tuples, preview, i18n("msg_desaturate_complete")

    components["desaturate_btn"].click(
        fn=on_desaturate,
        outputs=[components["desaturated_gallery"], components["desaturate_preview"], components["desaturate_status"]],
    )