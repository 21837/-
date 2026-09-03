# -*- coding: utf-8 -*-
"""
ReAct Agent 教学 demo（无框架，原生 function calling）

核心概念（面试必答）：
1. Agent = LLM(大脑) + Tools(手脚) + Loop(循环)
2. Function calling 的本质：模型只输出"我想调用哪个工具、传什么参数"的结构化意图，
   真正执行的是你的代码——模型不会算数，但会说"我要用计算器"
3. ReAct 循环：思考(Reason) → 行动(Act) → 观察(Observe) → 再思考...
   对应代码里的消息协议：assistant(带tool_calls) → 执行 → tool(回填结果) → 再喂给模型

消息协议（OpenAI 兼容格式）：
- user: 用户提问
- assistant: 模型回复（可能带 tool_calls 字段 = 工具调用意图）
- tool: 工具执行结果，用 tool_call_id 与 assistant 的调用关联

运行：python react_agent.py（需环境变量 ZAI_KEY）
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台 UTF-8，防 emoji 报错

KEY = os.environ["ZAI_KEY"]
BASE = "https://open.bigmodel.cn/api/paas/v4"
MODEL = "glm-5.3-flash"  # 便宜，够用；要更强换 glm-5.3

# ---------- 1. 工具定义（给模型看的"说明书"） ----------
# 模型靠这段 JSON 知道：有什么工具、干什么用、参数长什么样
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_prices",
            "description": "批量获取A股实时行情，返回每只股票的名称、现价、涨跌幅",
            "parameters": {
                "type": "object",
                "properties": {
                    "codes": {"type": "array", "items": {"type": "string"}, "description": "6位股票代码列表，如 [\"600795\", \"000725\"]"}
                },
                "required": ["codes"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "执行数学计算，支持 + - * / 和括号",
            "parameters": {
                "type": "object",
                "properties": {
                    "expr": {"type": "string", "description": "数学表达式，如 (10.5*100)"}
                },
                "required": ["expr"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间"   
        },
    },
]

# ---------- 2. 工具实现（真正干活的代码） ----------
def run_tool(name, args):
    """执行工具并返回结果字符串（要转成字符串喂回给模型）"""
    if name == "get_stock_prices":
        codes = args["codes"]
        # 腾讯 API 支持逗号拼接批量查询，前缀规则：6开头=沪(sh)，其他=深(sz)
        qs = ",".join(("sh" if c.startswith("6") else "sz") + c for c in codes)
        url = f"https://qt.gtimg.cn/q={qs}"
        with urllib.request.urlopen(url, timeout=10) as r:
            raw = r.read().decode("gbk")
        out = []
        for line in raw.strip().split(";"):
            parts = line.split("~")
            if len(parts) > 32 and parts[1]:
                out.append(f"{parts[1]}({parts[2]}) 现价{parts[3]} 涨跌幅{parts[32]}%")
        return " | ".join(out)
    if name == "calc":
        # ⚠️ 教学演示用 eval；生产环境禁止！应改用 ast.literal_eval 或安全计算库
        return str(eval(args["expr"]))
    if name == "get_time":
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "未知工具"

# ---------- 3. LLM 调用（OpenAI 兼容 /chat/completions） ----------
def call_llm(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "tools": TOOLS}).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + KEY)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

# ---------- 4. ReAct 主循环 ----------
def agent(question, max_steps=5):
    messages = [{"role": "system", "content": "你是量化助手。回答必须：1)只基于工具返回的数据 2)不提工具未提供的信息 3)计算步骤必须展示"}]
    messages.append({"role": "user", "content": question})
    print(f"🧠 用户：{question}\n")
    for step in range(max_steps):
        resp = call_llm(messages)
        msg = resp["choices"][0]["message"]

        # 情况 A：模型要调用工具（返回 tool_calls）
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                result = run_tool(name, args)
                print(f"  🔧 step{step+1}：调用 {name}({args})\n     → {result}")
                # 回填协议：assistant 消息原样追加 + tool 消息带 tool_call_id
                messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue  # 进入下一轮思考

        # 情况 B：模型给出最终答案
        print(f"✅ 最终回答：{msg['content']}")
        return

    print("⚠️ 达到最大步数，强制结束")

if __name__ == "__main__":
    agent(
        "帮我查国电电力(600795)、京东方A(000725)、绿的谐波(688017)今天的行情，按涨跌幅从高到低排序"
    )
