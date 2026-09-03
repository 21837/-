# -*- coding: utf-8 -*-
"""
FastAPI 版 agent 服务（教学 demo）—— 第 2 周阶段 B

把昨天的 react_agent.py 包成 HTTP 服务：
- 之前：python react_agent.py 只能命令行一问一答
- 现在：POST /chat 接口，任何程序（前端/脚本/微信机器人）都能调

架构关系（面试必答）：
  HTTP 请求 → FastAPI(路由/校验) → agent 循环(LLM+Tools) → HTTP 响应
  记忆层：session_id 维度的消息历史（内存 dict）

运行：
  1. pip install fastapi uvicorn
  2. 确认环境变量 ZAI_KEY 已设置（昨天的 key）
  3. python fastapi_server.py
  4. 另开终端测试：见文件底部 __main__ 注释里的 curl 命令

⚠️ 教学 demo 的简化（面试被问"生产环境怎么办"要能答）：
  - 记忆用内存 dict：多实例各自为政、重启即丢 → 生产用 Redis
  - eval 计算：昨天已标注，生产禁止 → 用 ast.literal_eval 或安全计算库
  - 无鉴权：任何人能调你的接口 → 生产加 API Key 校验
"""
import json
import os
import sys
import datetime
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# ---------- 复用昨天的工具（不重复造轮子） ----------
# run_tool: 真正执行工具的代码；TOOLS: 给模型看的工具说明书
# call_llm: OpenAI 兼容的模型调用；MODEL/BASE: 模型配置
from react_agent import run_tool, call_llm, TOOLS, MODEL, BASE

# ---------- 0. 启动前置检查 ----------
# import 时没有 ZAI_KEY 会 KeyError，这里给个清晰报错（面试题：服务启动失败怎么排查）
if not os.environ.get("ZAI_KEY"):
    print("❌ 未设置 ZAI_KEY 环境变量，服务拒绝启动。")
    print("   PowerShell 设置：$env:ZAI_KEY=\"你的key\"")
    sys.exit(1)

# ---------- 1. 应用与记忆层 ----------
app = FastAPI(title="量化助手 Agent 服务", version="0.1")

# 多轮记忆：session_id -> 该会话的 messages 历史
# TODO(你)：现在的字典只增不减，长期运行会撑爆内存。怎么解决？(提示：设上限/过期清理)
SESSIONS = {}

SYSTEM_PROMPT = "你是量化助手。回答必须：1)只基于工具返回的数据 2)不提工具未提供的信息 3)计算步骤必须展示"

# ---------- 2. 请求/响应模型（FastAPI 自动做格式校验，格式错返回 422） ----------
class ChatRequest(BaseModel):
    query: str                                # 用户问题，必填
    session_id: Optional[str] = None          # 不带 = 自动开新会话

class ChatResponse(BaseModel):
    answer: str                               # agent 最终回答
    session_id: str                           # 记住它，下次提问带上 = 续上记忆
    tool_calls: int                           # 本轮调用了几次工具（面试讲 agent 循环用得上）

# ---------- 3. agent 循环（带记忆版） ----------
def run_agent(session_id: str, question: str, max_steps: int = 5) -> tuple[str, int]:
    """返回 (最终回答, 工具调用次数)。与昨天 react_agent.py 的循环几乎一样，
    唯一区别：messages 从 SESSIONS 里取，而不是每次新建 —— 这就是"记忆"。"""
    messages = SESSIONS.get(session_id)
    if messages is None:                      # 新会话 → 初始化 system
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        SESSIONS[session_id] = messages
    messages.append({"role": "user", "content": question})

    tool_count = 0
    for step in range(max_steps):
        try:
            resp = call_llm(messages)
        except Exception as e:
            # 网络/模型服务异常 → 抛给上层转成 HTTP 500
            raise HTTPException(status_code=502, detail=f"模型调用失败: {e}")
        msg = resp["choices"][0]["message"]

        # 情况 A：模型要调用工具
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                    result = run_tool(name, args)
                except Exception as e:
                    result = f"工具执行出错: {e}"   # 工具失败不中断，把错误喂回模型让它自己处理
                # 回填协议（与昨天一致）：assistant 原样追加 + tool 带 tool_call_id
                messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                tool_count += 1
            continue

        # 情况 B：最终答案
        return msg["content"], tool_count

    return "⚠️ 达到最大步数，强制结束", tool_count

# ---------- 4. HTTP 接口 ----------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 无 session_id → 自动生成（uuid 保证不重，面试题：为什么不用时间戳？）
    session_id = req.session_id or uuid.uuid4().hex[:12]
    answer, tool_count = run_agent(session_id, req.query)
    return ChatResponse(answer=answer, session_id=session_id, tool_calls=tool_count)

# ---------- 5. 健康检查（部署后验证服务活着的最快方式） ----------
@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # host=0.0.0.0 允许局域网访问（部署到服务器必须这样）；开发想只看本机可改 127.0.0.1
