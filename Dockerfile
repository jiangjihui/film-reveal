FROM python:3.12-slim

WORKDIR /app

# 先安装依赖（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制源码、入口脚本和资源
COPY run.py .
COPY src/ ./src/
COPY image/ ./image/

# 非 root 用户运行（安全最佳实践）
RUN useradd --create-home appuser
USER appuser

EXPOSE 7860

CMD ["python", "run.py"]