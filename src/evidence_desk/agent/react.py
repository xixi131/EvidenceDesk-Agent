from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from evidence_desk.agent.tools import build_agent_tools
from evidence_desk.application.ports import ChunkRetriever, GitHubGateway, QueryEmbedder
from evidence_desk.application.ticket_service import TicketService

SYSTEM_PROMPT = """\
<角色>
你是 GitHub Actions 技术支持助手，尽力准确、可靠地帮助用户。
</角色>

<工具使用策略>
- 知识性问题（用法、概念、配置、故障排查）：调用 search_docs 检索官方文档，并在回答中引用返回的来源链接。
- 询问某次具体运行的状态或结论（会给出 owner、repo、run_id）：调用 get_workflow_run；需要定位是哪一步失败时再调 list_workflow_jobs。
- 运行结果必须来自工具，严禁用文档猜测运行状态。
- 问候或闲聊：直接、友好、简短地回应，不要调用任何工具。
- 用户主动提供了值得长期记住的个人信息（自我介绍、明确的偏好设置）：调用 save_user_memory 记住。
- 需要了解这个用户的背景信息才能更贴切地回答（用户提到"之前说过""你还记得吗"等）：调用 recall_user_memory 检索。
- 已经用过文档和 GitHub 工具仍解决不了用户的问题：调用 create_support_ticket 创建支持工单
  （这个操作会先经过人工审批才会真正执行，不需要你自己在对话里先问用户同意）。
</工具使用策略>

<回答准则>
- 只依据工具返回的内容作答，不编造。
- 工具与文档都无法提供依据时，如实说明你不知道。
- 使用简体中文，简洁、准确。
</回答准则>
"""


def build_react_agent(
    model: BaseChatModel,
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    gateway: GitHubGateway,
    *,
    top_k: int,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    summary_trigger_tokens: int | None = None,
    summary_keep_messages: int = 6,
    store: BaseStore | None = None,
    memory_top_k: int = 5,
    ticket_service: TicketService | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """装配并编译一个绑定工具的 ReAct Agent（checkpointer 提供多轮记忆）。

    这是 ReAct Agent 的「组装点」。调用链：
      main.py(组合根) → build_react_agent → create_agent(内部搭好 ReAct 循环)
    model 作为参数注入：生产传 ChatOpenAI，测试传假聊天模型，所以能离线测。

    summary_trigger_tokens 不传（None）时不装摘要中间件，行为和之前完全一样
    （现有测试因此不用改）；main.py 会传具体阈值来正式启用 M-2。

    store 不传（None）时不注册长期记忆工具（M-3），行为跟之前一样；
    main.py 会传 InMemoryStore 正式启用。

    ticket_service 不传（None）时不注册 create_support_ticket 写工具（P4-05）；
    main.py 会传具体实现正式启用。
    """
    # ① 把检索 / GitHub 能力包成「工具清单」：每个工具的 docstring+类型 = 发给 LLM 的说明书
    #    store/memory_top_k 传下去：build_agent_tools 内部按 store 是否为 None
    #    决定要不要多注册 save_user_memory/recall_user_memory 这两个工具（M-3）；
    #    ticket_service 同理决定要不要多注册 create_support_ticket（P4-05）。
    tools = build_agent_tools(
        embedder,
        retriever,
        gateway,
        top_k=top_k,
        store=store,
        memory_top_k=memory_top_k,
        ticket_service=ticket_service,
    )

    # ②（M-2）上下文超限策略：SummarizationMiddleware 挂在 create_agent 的
    #    before_model 钩子上——也就是「每次真正调 LLM 之前都会先跑一遍」。
    #    它按（近似）token 数判断要不要摘要旧消息，触发后：
    #      旧消息 →（用同一个 model 生成一段摘要文本）→ 替换成
    #      「摘要 HumanMessage + 最近 summary_keep_messages 条原始消息」，
    #    并且这个替换结果会写回 checkpointer，所以是持久化压缩，不是临时展示。
    #    它还会保证不会把 AIMessage 的 tool_calls 和对应 ToolMessage 拆开保留/摘要。
    middleware: list[Any] = []
    if summary_trigger_tokens is not None:
        middleware.append(
            SummarizationMiddleware(
                model,
                trigger=("tokens", summary_trigger_tokens),
                keep=("messages", summary_keep_messages),
            )
        )

    # ③（阶段 5 HITL）写操作审批。逐行拆开讲：
    #
    # -- if ticket_service is not None: --
    #    判断条件是「is not None」，不是判断某个值等不等于某个具体常量。
    #    ticket_service 这个参数默认值是 None（见函数签名）；main.py 传了具体
    #    的 TicketService 实例进来，这个判断才会是 True。跟②的
    #    summary_trigger_tokens、①的 store 是同一个套路：「有没有传这个依赖」
    #    直接决定「要不要装这份能力」——create_support_ticket 工具本身也是
    #    靠同一个 ticket_service 是否为 None 来决定注不注册（见 tools.py）。
    #    这里为什么要重复判断一次：因为“注册了写工具”和“给写工具挂审批”是
    #    两件独立的事，缺了这个判断，万一 ticket_service 是 None（写工具根本
    #    没注册），却还去配置“拦截 create_support_ticket”，实际上没有意义
    #    （没有这个工具可拦截），属于无意义的空判断，所以要跟①保持同一个
    #    判断条件，保证「审批」和「工具」总是同时存在或同时不存在。
    #
    # -- middleware.append(HumanInTheLoopMiddleware(...)) --
    #    append 进 middleware 这个列表的，是「一个配置好的中间件对象」——
    #    HumanInTheLoopMiddleware(...) 这一整块是在「构造对象」，构造完了才
    #    append。它跟②的 SummarizationMiddleware(...) 是完全一样的用法：
    #    构造一个实现了某些钩子方法的对象，塞进这个列表，最后一起交给下面
    #    ④的 create_agent(middleware=middleware)。只不过这个中间件实现的是
    #    after_model 钩子（模型刚吐出 tool_calls、工具还没真正执行的那个
    #    时间点），②的 SummarizationMiddleware 实现的是 before_model 钩子
    #    （调模型之前）——挂钩位置不同，但「构造对象 -> append」这个动作
    #    本身是同一件事。
    #
    # -- interrupt_on={"create_support_ticket": {"allowed_decisions": [...]}} --
    #    这是构造 HumanInTheLoopMiddleware 时传的唯一参数，一个字典：
    #      key   = 工具的名字（字符串），必须跟 tools.py 里 @tool 装饰的那个
    #              函数名一模一样（create_support_ticket），中间件靠这个名字
    #              去匹配「模型这次调用的是不是这个工具」；
    #      value = 这个工具允许哪些审批结果，["approve", "reject"] 表示只能
    #              批准或拒绝（库还支持 "edit"/"respond"，我们没用到，所以
    #              没写进这个列表——列表里没有的决定类型，提交了会被拒绝）。
    #    没写进这个字典里的工具（search_docs、get_workflow_run 等只读工具）
    #    默认「自动放行、不拦截」——这是 HumanInTheLoopMiddleware 自己的行为
    #    （它的官方文档写了：没配置的工具 auto-approved by default），我们
    #    不需要为每个只读工具再显式写一行"不拦截"。
    if ticket_service is not None:
        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_support_ticket": {"allowed_decisions": ["approve", "reject"]}
                }
            )
        )

    # ④ create_agent 内部搭好 ReAct 循环：
    #    [调模型（先过 middleware.before_model）] →（模型吐 tool_calls 就执行工具、
    #    把结果回喂）→ [再调模型] → … → 无 tool_calls 时收尾
    #    checkpointer：按 thread_id 存/取会话历史 = 短期多轮记忆（M-1/M-2）；传 None 则无记忆（单轮）
    #    store：跨会话的长期记忆存储（M-3），挂在这里之后，图执行期间任何节点/工具
    #    内部调用 get_store() 拿到的就是这同一个实例（tools.py 里就是这么用的）。
    return create_agent(
        model,
        tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        middleware=middleware,
        store=store,
    )
