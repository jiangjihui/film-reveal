"""
黑白胶卷翻拍后期处理工具 — Gradio UI 主入口

功能：旋转 → 裁切 → 去色 → 反转，支持批量处理多张图片。
支持中文、英文、日文三种语言，用户通过页面底部设置面板切换。
"""

import gradio as gr
import zipfile
import tempfile
import os
from PIL import Image

from film_reveal.state import AppState
from film_reveal.i18n import get_i18n
from film_reveal.processing import (
    auto_detect_crop_boundaries,
    draw_crop_overlay,
    rotate_image,
    apply_crop_with_offsets,
    desaturate,
    invert,
)
from film_reveal.steps import (
    create_rotate_ui, bind_rotate_events,
    create_crop_ui, bind_crop_events,
    create_desaturate_ui, bind_desaturate_events,
    create_invert_ui, bind_invert_events,
)
from film_reveal.steps.common import make_thumbnail


# ── 自定义 CSS ──
# 限制页面最大宽度，参考 GitHub 的 container-xl 布局（1280px），
# 避免 PC 宽屏下图片预览铺满全屏导致竖向图片无法一屏显示完整。
CUSTOM_CSS = """
.gradio-container {
    max-width: 1280px;
    margin: 0 auto;
}
"""


def create_app():
    """创建 Gradio 应用，组装所有步骤和事件。"""

    state = AppState()
    i18n = get_i18n()

    with gr.Blocks(title=i18n("blocks_title")) as demo:

        # ── 标题 ──
        gr.Markdown(i18n("app_title"))
        gr.Markdown(i18n("app_description"))

        # ── 上传区 ──
        gr.Markdown(i18n("upload_section"))
        with gr.Row():
            upload_files = gr.File(
                label=i18n("upload_label"),
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            original_gallery = gr.Gallery(
                label=i18n("original_gallery_label"), columns=4, height="auto", object_fit="contain",
            )

        # ── 各步骤 UI ──
        rotate_components = create_rotate_ui(i18n)
        crop_components = create_crop_ui(i18n)
        desaturate_components = create_desaturate_ui(i18n)
        invert_components = create_invert_ui(i18n)

        # ── 批量操作 ──
        gr.Markdown(i18n("batch_section"))
        with gr.Row():
            process_all_btn = gr.Button(i18n("process_all_btn"), variant="primary")
            download_btn = gr.Button(i18n("download_btn"), variant="secondary")
        with gr.Row():
            download_file = gr.File(label=i18n("download_file_label"))
            process_all_status = gr.Textbox(label=i18n("batch_status_label"), interactive=False)

        # ── 事件绑定 ──

        # ── 上传事件 ──
        def on_upload(files):
            """处理上传事件：加载所有图片并初始化旋转和裁切参数。"""
            if not files:
                return (
                    [], [], [], [], [],
                    None,
                    0, 0.0,
                    0, 0, 0, 0,
                    i18n("msg_upload_first"),
                )

            state.reset()
            for f in files:
                try:
                    img = Image.open(f).convert("RGB")
                    state.original_images.append(img)
                except Exception:
                    # 跳过损坏的图片，不崩溃
                    continue

            if not state.original_images:
                return (
                    [], [], [], [], [],
                    None,
                    0, 0.0,
                    0, 0, 0, 0,
                    i18n("msg_all_images_failed"),
                )

            # 初始化旋转参数
            for i in range(len(state.original_images)):
                state.rotation_params[i] = {"base_angle": 0, "fine_angle": 0.0}
                state.rotated_images.append(None)

            # 为每张图自动检测裁切边界（基于原图）
            for i, img in enumerate(state.original_images):
                boundaries = auto_detect_crop_boundaries(img)
                state.crop_params[i] = {
                    "base_boundaries": boundaries,
                    "offsets": {"top": 0, "bottom": 0, "left": 0, "right": 0},
                }

            # Gallery 显示原图（使用缩略图提升性能）
            gallery_images = [(make_thumbnail(img), "#" + str(i+1)) for i, img in enumerate(state.original_images)]

            # 显示第一张图的裁切预览
            state.selected_index = 0
            first_preview = draw_crop_overlay(
                state.original_images[0],
                state.crop_params[0]["base_boundaries"],
                state.crop_params[0]["offsets"],
            )

            return (
                gallery_images, [], [], [],
                first_preview,
                0, 0.0,
                0, 0, 0, 0,
                i18n("msg_uploaded"),
            )

        upload_files.upload(
            fn=on_upload,
            inputs=upload_files,
            outputs=[
                original_gallery,
                rotate_components["rotated_gallery"],
                crop_components["cropped_gallery"],
                invert_components["inverted_gallery"],
                crop_components["crop_preview"],
                rotate_components["rotation_base_display"],
                rotate_components["rotation_slider"],
                crop_components["top_slider"],
                crop_components["bottom_slider"],
                crop_components["left_slider"],
                crop_components["right_slider"],
                crop_components["crop_status"],
            ],
        )

        # ── 原图 Gallery 选中事件 ──
        def on_gallery_select(evt: gr.SelectData):
            """Gallery 选中某张图片时，更新旋转和裁切预览及滑块值。"""
            if not state.original_images:
                return None, 0, 0.0, 0, 0, 0, 0

            idx = evt.index
            if idx < 0 or idx >= len(state.original_images):
                return None, 0, 0.0, 0, 0, 0, 0

            state.selected_index = idx

            rot_params = state.rotation_params[idx]
            base_angle = rot_params["base_angle"]
            fine_angle = rot_params["fine_angle"]

            crop_params = state.crop_params[idx]

            working_img = state.get_working_image(idx)
            preview = draw_crop_overlay(
                working_img,
                crop_params["base_boundaries"],
                crop_params["offsets"],
            )

            return (
                preview,
                base_angle, fine_angle,
                crop_params["offsets"]["top"],
                crop_params["offsets"]["bottom"],
                crop_params["offsets"]["left"],
                crop_params["offsets"]["right"],
            )

        original_gallery.select(
            fn=on_gallery_select,
            outputs=[
                crop_components["crop_preview"],
                rotate_components["rotation_base_display"],
                rotate_components["rotation_slider"],
                crop_components["top_slider"],
                crop_components["bottom_slider"],
                crop_components["left_slider"],
                crop_components["right_slider"],
            ],
        )

        # ── 各步骤事件绑定 ──
        bind_rotate_events(rotate_components, state, i18n)
        bind_crop_events(crop_components, state, i18n)
        bind_desaturate_events(desaturate_components, state, i18n)
        bind_invert_events(invert_components, state, i18n)

        # ── 一键处理事件 ──
        def on_process_all():
            """一键完成全部步骤：使用当前旋转参数 → 自动裁切 → 去色 → 反转。"""
            if not state.original_images:
                return [], [], [], None, i18n("msg_upload_first")

            # 保留旋转参数，清空下游步骤缓存
            state.cropped_images = []
            state.desaturated_images = []
            state.inverted_images = []

            rotated_gallery = []
            cropped_gallery = []
            inverted_gallery = []

            for i, img in enumerate(state.original_images):
                # 使用当前旋转参数
                total_angle = state.get_total_rotation(i)
                rotated = rotate_image(img, total_angle) if total_angle != 0 else img
                state.rotated_images[i] = rotated
                rotated_gallery.append((make_thumbnail(rotated), "#" + str(i+1)))

                # 使用用户已微调的裁切参数（与预览中显示的完全一致）
                crop_params = state.crop_params[i]
                boundaries = crop_params["base_boundaries"]
                offsets = crop_params["offsets"]
                cropped = apply_crop_with_offsets(rotated, boundaries, offsets)
                state.cropped_images.append(cropped)
                cropped_gallery.append((make_thumbnail(cropped), "#" + str(i+1)))

                # 去色 + 反转
                desaturated_img = desaturate(cropped)
                inverted_img = invert(desaturated_img)
                state.desaturated_images.append(desaturated_img)
                state.inverted_images.append(inverted_img)
                inverted_gallery.append((make_thumbnail(inverted_img, 1000), "#" + str(i+1)))

            preview = state.inverted_images[state.selected_index]
            return rotated_gallery, cropped_gallery, inverted_gallery, preview, i18n("msg_batch_complete")

        process_all_btn.click(
            fn=on_process_all,
            outputs=[
                rotate_components["rotated_gallery"],
                crop_components["cropped_gallery"],
                invert_components["inverted_gallery"],
                invert_components["invert_preview"],
                process_all_status,
            ],
        )

        # ── 下载事件 ──
        def on_download_all():
            """将所有最终正片打包为 ZIP 文件供下载。"""
            if not state.inverted_images:
                return None, i18n("msg_no_download")

            tmpdir = tempfile.mkdtemp()
            zip_path = os.path.join(tmpdir, "film_negatives_processed.zip")

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, img in enumerate(state.inverted_images):
                    filename = f"positive_{i+1}.jpg"
                    img_path = os.path.join(tmpdir, filename)
                    img.save(img_path, "JPEG", quality=95)
                    zf.write(img_path, filename)

            return zip_path, i18n("msg_downloaded")

        download_btn.click(
            fn=on_download_all,
            outputs=[download_file, process_all_status],
        )

    # 将 i18n 和自定义 CSS 附加到 demo 对象上，方便 launch 时使用
    demo.i18n = i18n
    demo.custom_css = CUSTOM_CSS
    return demo


# ── 启动 ──
if __name__ == "__main__":
    demo = create_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, i18n=demo.i18n, theme=gr.themes.Soft())