# 基础镜像：python 官方 3.10-slim（小+够用，react_agent 用 3.10 跑的）
FROM python:3.10-slim

# 工作目录
WORKDIR /app

# ① 先复制 requirements.txt 并 pip install（利用镜像层缓存：依赖不变就不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ② 复制代码
COPY . .

# ③ 暴露端口（和 uvicorn 的 port 对上）
EXPOSE 8000

# ④ 启动命令
CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
