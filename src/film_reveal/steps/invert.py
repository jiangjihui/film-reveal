"""
黑白胶卷翻拍后期处理 — 反转步骤

包含 UI 组件创建、事件绑定和反转回调函数。
使用 Gradio I18n 实现多语言支持。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import invert
from film_reveal.steps.common import batch_process


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_invert_ui(i18n) -> dict:
    """创建反转步骤的 UI 组件，返回组件引用字典。

    Args:
        i18n: Gradio I18n 实例，用于多语言翻译
    """
    components = {}

    gr.Markdown(i18n("invert_section"))
    gr.Markdown(i18n("invert_description"))

    with gr.Row():
        with gr.Column(scale=1):
            components["invert_btn"] = gr.Button(i18n("invert_btn"), variant="primary")
            components["invert_status"] = gr.Textbox(label=i18n("invert_status_label"), interactive=False)
        with gr.Column(scale=2):
            components["invert_preview"] = gr.Image(label=i18n("invert_preview_label"), type="pil")

    components["inverted_gallery"] = gr.Gallery(
        label=i18n("inverted_gallery_label"), columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_invert_events(components: dict, state: AppState, i18n):
    """绑定反转步骤的事件回调。

    Args:
        components: 反转步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
        i18n: Gradio I18n 实例（通过闭包注入）
    """
    def on_invert():
        """对所有去色后图片执行反转处理。"""
        if not state.desaturated_images:
            return [], None, i18n("msg_invert_first")

        results, gallery_tuples = batch_process(
            state,
            source_list_name="desaturated_images",
            process_fn=invert,
            target_list_name="inverted_images",
            clear_downstream_from="inverted",
        )

        preview = results[state.selected_index]
        return gallery_tuples, preview, i18n("msg_invert_complete")

    components["invert_btn"].click(
        fn=on_invert,
        outputs=[components["inverted_gallery"], components["invert_preview"], components["invert_status"]],
    )