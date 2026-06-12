"""
黑白胶卷翻拍后期处理 — 去色步骤

包含 UI 组件创建、事件绑定和去色回调函数。
"""

import gradio as gr

from film_reveal.state import AppState
from film_reveal.processing.core import desaturate
from film_reveal.steps.common import batch_process


# ── UI 创建 ────────────────────────────────────────────────────────────

def create_desaturate_ui() -> dict:
    """创建去色步骤的 UI 组件，返回组件引用字典。

    必须在 gr.Blocks() 上下文中调用。
    """
    components = {}

    gr.Markdown("### 🎨 Step 2: 去色")
    gr.Markdown("> 将 RGB 照片转为灰度，去除手机拍照产生的偏色和色温干扰。")

    with gr.Row():
        with gr.Column(scale=1):
            components["desaturate_btn"] = gr.Button("🎨 去色处理", variant="primary")
            components["desaturate_status"] = gr.Textbox(label="去色状态", interactive=False)
        with gr.Column(scale=2):
            components["desaturate_preview"] = gr.Image(label="去色预览", type="pil")

    components["desaturated_gallery"] = gr.Gallery(
        label="去色结果", columns=4, height="auto", object_fit="contain",
    )

    return components


# ── 事件绑定 ────────────────────────────────────────────────────────────

def bind_desaturate_events(components: dict, state: AppState):
    """绑定去色步骤的事件回调。

    Args:
        components: 去色步骤的 UI 组件字典
        state: 应用状态实例（通过闭包注入）
    """
    def on_desaturate():
        """对所有裁切后图片执行去色处理。"""
        if not state.cropped_images:
            return [], None, "请先完成裁切步骤"

        results, gallery_tuples = batch_process(
            state,
            source_list_name="cropped_images",
            process_fn=desaturate,
            target_list_name="desaturated_images",
            clear_downstream_from="desaturated",
            label_prefix="去色后",
        )

        preview = results[state.selected_index]
        return gallery_tuples, preview, "去色完成！可继续进行反转处理"

    components["desaturate_btn"].click(
        fn=on_desaturate,
        outputs=[components["desaturated_gallery"], components["desaturate_preview"], components["desaturate_status"]],
    )