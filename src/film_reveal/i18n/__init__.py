"""
黑白胶卷翻拍后期处理 — 多语言支持

提供 Gradio I18n 实例，支持中文、英文、日文。
"""

from gradio.i18n import I18n
from .translations import TRANSLATIONS


def get_i18n() -> I18n:
    """创建 Gradio I18n 实例，传入三语翻译字典。

    使用方式：
        i18n = get_i18n()
        gr.Button(i18n("auto_tilt_btn"))  # 前端自动翻译
        demo.launch(i18n=i18n, ...)        # 传入 i18n 实例
    """
    return I18n(**TRANSLATIONS)