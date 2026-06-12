"""
黑白胶卷翻拍后期处理工具 — Gradio UI 主入口

功能：旋转 → 裁切 → 去色 → 反转，支持批量处理多张图片。

此文件负责：
- 组装各步骤的 UI 和事件绑定
- 处理跨步骤回调（上传、选中、一键处理、下载）
- 启动 Gradio 应用
"""

import gradio as gr
import zipfile
import tempfile
import os
from PIL import Image

from film_reveal.state import AppState
from film_reveal.processing import (
    auto_detect_crop_boundaries,
    draw_crop_overlay,
    rotate_image,
    apply_crop_with_offsets,
    desaturate,
    invert,
    detect_crop_on_rotated,
)
from film_reveal.steps import (
    create_rotate_ui, bind_rotate_events,
    create_crop_ui, bind_crop_events,
    create_desaturate_ui, bind_desaturate_events,
    create_invert_ui, bind_invert_events,
)


def create_app():
    """创建 Gradio 应用，组装所有步骤和事件。"""

    state = AppState()

    with gr.Blocks(title="黑白胶卷翻拍后期处理", theme=gr.themes.Soft()) as demo:

        # ── 标题 ──
        gr.Markdown("# 🎞️ 黑白胶卷翻拍后期处理工具")
        gr.Markdown(
            "> 上传手机翻拍的黑白胶卷负片照片，依次完成 **旋转 → 裁切 → 去色 → 反转** 四个步骤，将负片转为正片。"
        )

        # ── 上传区 ──
        gr.Markdown("### 📤 上传翻拍照片")
        with gr.Row():
            upload_files = gr.File(
                label="选择照片（支持多张）",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            original_gallery = gr.Gallery(
                label="原图", columns=4, height="auto", object_fit="contain",
            )

        # ── 各步骤 UI ──
        rotate_components = create_rotate_ui()
        crop_components = create_crop_ui()
        desaturate_components = create_desaturate_ui()
        invert_components = create_invert_ui()

        # ── 批量操作 ──
        gr.Markdown("### ⚡ 批量操作")
        with gr.Row():
            process_all_btn = gr.Button("⚡ 一键完成全部步骤", variant="primary")
            download_btn = gr.Button("📦 下载全部结果（ZIP）", variant="secondary")
        with gr.Row():
            download_file = gr.File(label="下载 ZIP 文件")
            process_all_status = gr.Textbox(label="批量操作状态", interactive=False)

        # ── 事件绑定 ──

        # 跨步骤回调（定义在这里，因为它们涉及多个步骤的组件）
        # 所有回调通过闭包捕获 state

        # ── 上传事件 ──
        def on_upload(files):
            """处理上传事件：加载所有图片并初始化旋转和裁切参数。"""
            if not files:
                return (
                    [], [], [], [], [],
                    None,
                    0, 0.0,
                    0, 0, 0, 0,
                    "请上传图片",
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
                    "所有图片加载失败，请检查文件",
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

            # Gallery 显示原图
            gallery_images = [(img, f"原图 #{i+1}") for i, img in enumerate(state.original_images)]

            # 显示第一张图的裁切预览
            state.selected_index = 0
            first_preview = draw_crop_overlay(
                state.original_images[0],
                state.crop_params[0]["base_boundaries"],
                state.crop_params[0]["offsets"],
            )

            return (
                gallery_images, [], [], [], [],
                first_preview,
                0, 0.0,
                0, 0, 0, 0,
                f"已上传 {len(state.original_images)} 张图片",
            )

        upload_files.upload(
            fn=on_upload,
            inputs=upload_files,
            outputs=[
                original_gallery,
                rotate_components["rotated_gallery"],
                crop_components["cropped_gallery"],
                desaturate_components["desaturated_gallery"],
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
        bind_rotate_events(rotate_components, state, other_components={"crop_preview": crop_components["crop_preview"]})
        bind_crop_events(crop_components, state)
        bind_desaturate_events(desaturate_components, state)
        bind_invert_events(invert_components, state)

        # ── 一键处理事件 ──
        def on_process_all():
            """一键完成全部步骤：使用当前旋转参数 → 自动裁切 → 去色 → 反转。"""
            if not state.original_images:
                return [], [], [], [], None, "请先上传图片"

            # 保留旋转参数，清空下游步骤缓存
            state.cropped_images = []
            state.desaturated_images = []
            state.inverted_images = []

            rotated_gallery = []
            cropped_gallery = []
            desaturated_gallery = []
            inverted_gallery = []

            for i, img in enumerate(state.original_images):
                # 使用当前旋转参数
                total_angle = state.get_total_rotation(i)
                rotated = rotate_image(img, total_angle) if total_angle != 0 else img
                state.rotated_images[i] = rotated
                rotated_gallery.append((rotated, f"旋转后 #{i+1}"))

                # 对旋转后图片检测裁切边界（正确处理扩展画布）
                boundaries = detect_crop_on_rotated(rotated, img)
                cropped = apply_crop_with_offsets(rotated, boundaries, {"top": 0, "bottom": 0, "left": 0, "right": 0})
                state.cropped_images.append(cropped)
                cropped_gallery.append((cropped, f"裁切后 #{i+1}"))

                # 更新裁切参数
                state.crop_params[i] = {
                    "base_boundaries": boundaries,
                    "offsets": {"top": 0, "bottom": 0, "left": 0, "right": 0},
                }

                # 去色 + 反转
                desaturated_img = desaturate(cropped)
                inverted_img = invert(desaturated_img)
                state.desaturated_images.append(desaturated_img)
                state.inverted_images.append(inverted_img)
                desaturated_gallery.append((desaturated_img, f"去色后 #{i+1}"))
                inverted_gallery.append((inverted_img, f"正片 #{i+1}"))

            preview = state.inverted_images[state.selected_index]
            return rotated_gallery, cropped_gallery, desaturated_gallery, inverted_gallery, preview, "一键处理完成！所有步骤已自动执行"

        process_all_btn.click(
            fn=on_process_all,
            outputs=[
                rotate_components["rotated_gallery"],
                crop_components["cropped_gallery"],
                desaturate_components["desaturated_gallery"],
                invert_components["inverted_gallery"],
                invert_components["invert_preview"],
                process_all_status,
            ],
        )

        # ── 下载事件 ──
        def on_download_all():
            """将所有最终正片打包为 ZIP 文件供下载。"""
            if not state.inverted_images:
                return None, "没有可下载的结果，请先完成处理"

            tmpdir = tempfile.mkdtemp()
            zip_path = os.path.join(tmpdir, "film_negatives_processed.zip")

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, img in enumerate(state.inverted_images):
                    filename = f"positive_{i+1}.jpg"
                    img_path = os.path.join(tmpdir, filename)
                    img.save(img_path, "JPEG", quality=95)
                    zf.write(img_path, filename)

            return zip_path, f"已打包 {len(state.inverted_images)} 张正片为 ZIP 文件"

        download_btn.click(
            fn=on_download_all,
            outputs=[download_file, process_all_status],
        )

    return demo


# ── 启动 ──
if __name__ == "__main__":
    demo = create_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())