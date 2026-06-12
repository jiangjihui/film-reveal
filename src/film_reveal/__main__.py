"""
黑白胶卷翻拍后期处理工具 — 命令行入口

使用方式: python -m film_reveal
"""

from film_reveal.app import create_app

demo = create_app()
demo.launch(server_name="127.0.0.1", server_port=7860)