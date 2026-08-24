# ADR-004：采用 LLM 驱动的 ReAct Agent（替换规则分诊 + 写死路由）

- 状态：已接受
- 日期：2026-08-23

## 背景

阶段 3/4 最初实现为「规则分诊 + 写死路由 + 模板回答」：`classify_intent` 用正则判断意图，
GitHub 工具由代码规则触发并直接返回模板文本，LLM 不参与路由与工具决策。

该实现有明显缺陷：
- 纯规则路由无法优雅处理开放输入（例如问候「hello」会被当成查不到的知识而拒答）；
- 工具调用不是 LLM function calling，模型没有「自主决定用哪个工具、填什么参数、如何措辞」；
- 与「Agent」的定位不符——真正的 Agent 应由 LLM 驱动决策，代码只兜住危险动作。

## 决策

改为 **LLM 驱动的 ReAct 单脑 Agent**：

- 一个支持 function calling 的聊天模型（`langchain-openai` 的 `ChatOpenAI`，可配中转站 Base URL）
  绑定一组只读工具，由 **LLM 自己决定** 是否调用、调用哪个、填什么参数，并根据工具结果措辞。
- 工具（复用已有能力）：
  - `search_docs`：向量检索官方文档，返回带来源的片段（知识问答 + 引用）；
  - `get_workflow_run` / `list_workflow_jobs`：调 `GitHubGateway` 取真实运行事实。
- 用 LangGraph 的 `create_react_agent` 组装 ReAct 循环；用递归/步数上限熔断防止无限循环。
- 问候/闲聊/无法回答由 LLM 直接得体处理，不再硬性拒答。

## 确定性护栏（保留）

「LLM 决策，代码兜底危险动作」：
- **不可逆的写操作（取消/重跑）不作为普通工具暴露给 LLM**，必须走人工审批（阶段 5）；
- 递归/步数上限、工具错误统一为稳定错误码（沿用 AppError）。

## 影响

- 新增依赖 `langchain-openai`；Agent 路径改用 `ChatOpenAI`（无 Agent 的 `/api/v1/chat`
  仍可保留原 `RagAnswerService` 证据约束回答）。
- 前提：所用模型/中转站需支持 OpenAI function calling。
- 离线测试用假聊天模型脚本化 `tool_calls`，保证 CI 不依赖真实模型。
- 取舍：可控性/可预测性下降、成本上升、调试更难；以「假模型测试 + 步数熔断 + 写操作护栏」缓解。

## 被取代

ADR 之前阶段 3/4 的「规则分诊 + 写死路由」实现（保留在 git 历史中，commit 285e293/56467c5）。
