"""
黑白胶卷翻拍后期处理工具 — 启动脚本

从项目根目录运行: python run.py
"""

import sys
import os
import gradio as gr

# 将 src/ 目录添加到 Python 路径，使 film_reveal 包可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from film_reveal.app import create_app

if __name__ == "__main__":
    demo = create_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, i18n=demo.i18n, theme=gr.themes.Soft())