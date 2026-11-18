FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

RUN pip install --no-cache-dir "fastmcp>=4.2.1,<5"

WORKDIR /app
COPY server.py fastmcp.json ./

EXPOSE 8109

# 容器内已经装好依赖，用 --skip-env 跳过 uv 环境创建
CMD ["fastmcp", "run", "fastmcp.json", "--skip-env", "--transport", "http", "--host", "0.0.0.0", "--port", "8109"]
