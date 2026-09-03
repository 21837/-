# ReAct Agent 教学 Demo（零框架实现）

从零实现 Agent 核心循环，不依赖 LangChain / Dify 等任何框架。

**核心概念**：
- Agent = LLM(大脑) + Tools(手脚) + Loop(循环)
- Function calling 本质：模型只输出"想调用哪个工具、传什么参数"的结构化意图，真正执行的是你的代码
- ReAct 循环：思考(Reason) → 行动(Act) → 观察(Observe) → 再思考...

## 文件

| 文件 | 说明 |
|---|---|
| `react_agent.py` | ReAct 循环实现（原生 function calling，OpenAI 兼容消息协议） |
| `fastapi_server.py` | HTTP 服务封装（POST /chat 调用 Agent） |
| `Dockerfile` | 容器化部署（进行中） |
| `requirements.txt` | fastapi + uvicorn |

## 运行

```bash
# 需设置环境变量（模型 API key，代码不内置任何密钥）
export ZAI_KEY=your_key    # Linux/Mac
$env:ZAI_KEY="your_key"    # Windows PowerShell

python react_agent.py      # 命令行对话
python fastapi_server.py   # 起 HTTP 服务
```

## 状态

- 2026-09：本地验证跑通，Docker 部署进行中
- 代码注释含面试讲解（Agent 本质 / 消息协议 / 循环机制 / 服务启动排查），见源码 docstring
