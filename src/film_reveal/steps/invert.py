"""
黑白胶卷翻拍后期处理 — 反转步骤

包含 UI 组件创建、事件绑定和反转回调函数。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import invert
from film_reveal.steps.common import batch_process


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_invert_ui() -> dict:
    """创建反转步骤的 UI 组件，返回组件引用字典。

    必须在 gr.Blocks() 上下文中调用。
    """
    components = {}

    gr.Markdown("### 🔄 Step 3: 反转")
    gr.Markdown("> 将黑白负片反转为正片，还原真实的明暗关系。")

    with gr.Row():
        with gr.Column(scale=1):
            components["invert_btn"] = gr.Button("🔄 反转处理", variant="primary")
            components["invert_status"] = gr.Textbox(label="反转状态", interactive=False)
        with gr.Column(scale=2):
            components["invert_preview"] = gr.Image(label="反转预览", type="pil")

    components["inverted_gallery"] = gr.Gallery(
        label="最终正片", columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_invert_events(components: dict, state: AppState):
    """绑定反转步骤的事件回调。

    Args:
        components: 反转步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
    """
    def on_invert():
        """对所有去色后图片执行反转处理。"""
        if not state.desaturated_images:
            return [], None, "请先完成去色步骤"

        results, gallery_tuples = batch_process(
            state,
            source_list_name="desaturated_images",
            process_fn=invert,
            target_list_name="inverted_images",
            clear_downstream_from="inverted",
            label_prefix="正片",
        )

        preview = results[state.selected_index]
        return gallery_tuples, preview, "反转完成！最终正片已生成，可下载结果"

    components["invert_btn"].click(
        fn=on_invert,
        outputs=[components["inverted_gallery"], components["invert_preview"], components["invert_status"]],
    )