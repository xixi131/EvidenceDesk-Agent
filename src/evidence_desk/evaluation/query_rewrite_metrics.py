"""Query Rewrite 的风险指标：标识符保留率与虚构标识符注入（P6-02）。

Recall/MRR 只能告诉你"改写后检索变好还是变差了"，告诉不了你**为什么**。
P6-02 明确要求查三件事，其中两件靠这里的指标量化：

- 精确标识符是否丢失 → identifier_retention
- 是否引入虚构信息    → introduced_identifiers

（第三件"额外延迟"在评测脚本里直接掐表，不需要指标函数。）

为什么单独盯"标识符"而不是笼统看文本相似度：本项目 dev set 里 exact_identifier
是最大的一类（19/60 题），这类问题的正确答案强依赖 ACTIONS_STEP_DEBUG、
workflow_dispatch 这种精确写法。文本整体改得再顺，只要标识符被翻译掉或写错，
这一题就废了。所以要单独把标识符揪出来逐个核对。
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

# 一个 token 的长相：字母开头，后面可以跟字母数字和 _ . - ，
# 允许 owner/repo 这样的斜杠分段，以及 @v4 这样的版本后缀。
# 中文字符不在字符集里，所以"启用ACTIONS_STEP_DEBUG调试"里的标识符能被干净切出来。
_TOKEN_PATTERN = re.compile(
    r"[A-Za-z][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)*(?:@[A-Za-z0-9_.\-]+)?"
)

# GitHub Actions 的表达式语法 ${{ ... }}，整段当成一个标识符看待。
_EXPRESSION_PATTERN = re.compile(r"\$\{\{[^}]*\}\}")

# 匹配上 _TOKEN_PATTERN、但算不上"精确标识符"的通用词。
# 为什么要这份名单：GitHub 这种词按下面的驼峰规则会被判成标识符，可它在每条
# 问题里都出现、也永远不会被改写丢掉。把它算进保留率，等于往分母里塞一堆
# 必然得分的题，会把真实的丢失率稀释得看不出来。
_GENERIC_WORDS = frozenset(
    {
        "github",
        "json",
        "yaml",
        "yml",
        "api",
        "url",
        "uri",
        "http",
        "https",
        "id",
        "ui",
        "ci",
        "cd",
        "pr",
        "os",
    }
)


def _looks_like_identifier(token: str) -> bool:
    """判断一个英文 token 是不是"精确标识符"。

    三条规则，命中任意一条即可：
    1. 含有 _ / @ . - 这类连接符 —— workflow_dispatch、actions/checkout@v4、runs-on
    2. 全大写且长度 >= 2   —— ACTIONS_STEP_DEBUG、GITHUB_TOKEN（其实规则 1 也能中）
    3. 驼峰（小写后面直接跟大写）—— fromJSON、toJSON

    刻意做得保守：宁可漏判几个，也不要把 "the"、"use" 这种普通英文单词
    算成标识符。漏判的后果是保留率**偏乐观**（真实风险只会比报告的更大），
    这个偏向是可接受的——因为实验的用途是"找出改写会不会伤到标识符"，
    偏乐观的指标如果都已经报警，那结论只会更硬。
    """

    if len(token) < 2 or token.lower() in _GENERIC_WORDS:
        return False
    if any(sep in token for sep in ("_", "/", "@", ".", "-")):
        return True
    if token.isupper():
        return True
    return bool(re.search(r"[a-z][A-Z]", token))


def extract_identifiers(text: str) -> list[str]:
    """抽出文本里的精确标识符，按出现顺序去重。

    去重用"小写形式"做键，但返回值保留**第一次出现时的原始大小写**——
    大小写本身就是标识符的一部分（fromJSON 不是 fromjson），报告里要能看见原样。
    """

    found: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        key = token.lower()
        if key not in seen:
            seen.add(key)
            found.append(token)

    # 先把 ${{ ... }} 整段抽走，再把它从文本里挖掉，然后才扫普通 token。
    # 不挖掉的话，表达式内部的 github.event_name 会被 _TOKEN_PATTERN 再抽一遍，
    # 同一个东西就被数了两次，保留率的分母跟着虚高。
    for expression in _EXPRESSION_PATTERN.findall(text):
        _add(expression)
    remaining = _EXPRESSION_PATTERN.sub(" ", text)

    for token in _TOKEN_PATTERN.findall(remaining):
        if _looks_like_identifier(token):
            _add(token)

    return found


@dataclass(frozen=True, slots=True)
class IdentifierDiff:
    """一道题改写前后的标识符对比。"""

    kept: list[str]
    # 原问题里有、改写后没了 —— 直接对应 P6-02 的"精确标识符是否丢失"。
    lost: list[str]
    # 改写后冒出来、原问题里没有的 —— 对应"是否引入虚构信息"。
    # 注意这只是个**代理指标**，不等于幻觉：模型把"手动触发"补成
    # workflow_dispatch 属于合理的术语归一化，反而可能帮到检索。所以这一栏的
    # 用法是"捞出来给人看"，不是自动判错，报告里要逐条列原文供人工抽查。
    introduced: list[str]


def diff_identifiers(original: str, rewritten: str) -> IdentifierDiff:
    """对比改写前后的标识符，分出保留 / 丢失 / 新增三类。

    比较用小写：GITHUB_TOKEN 被写成 github_token 算保留，不算丢失。
    因为索引侧和查询侧的分词都会归一化大小写，这种改动不影响检索命中。
    真正致命的是整个标识符消失或被翻译成中文。
    """

    before = extract_identifiers(original)
    after_lower = {token.lower() for token in extract_identifiers(rewritten)}
    before_lower = {token.lower() for token in before}

    return IdentifierDiff(
        kept=[t for t in before if t.lower() in after_lower],
        lost=[t for t in before if t.lower() not in after_lower],
        introduced=[
            t for t in extract_identifiers(rewritten) if t.lower() not in before_lower
        ],
    )


@dataclass(frozen=True, slots=True)
class IdentifierSummary:
    """整个数据集上的标识符风险汇总。"""

    # 分母：原问题里至少含一个标识符的题数。不含标识符的题根本谈不上"丢失"，
    # 把它们算进来只会把保留率虚高。
    num_cases_with_identifier: int
    num_identifiers: int
    num_kept: int
    num_lost: int
    retention: float
    # 至少丢了一个标识符的题数 —— 比"标识符级保留率"更贴近用户感受：
    # 一道题只要丢一个关键标识符，这道题就可能整个答错。
    num_cases_with_loss: int
    num_cases_with_introduced: int


def summarize_identifiers(pairs: Sequence[tuple[str, str]]) -> IdentifierSummary:
    """对一批 (原问题, 改写后问题) 汇总标识符保留情况。

    收最朴素的字符串二元组而不是某个评测结果类型：跟 group_recall_by_tag
    一样的考虑，让这个模块不反向依赖 runner/脚本里的数据结构。
    """

    num_cases = 0
    total = kept = lost = 0
    cases_with_loss = cases_with_introduced = 0

    for original, rewritten in pairs:
        diff = diff_identifiers(original, rewritten)
        if diff.introduced:
            cases_with_introduced += 1
        # 原问题没有标识符的题，跳过保留率统计（但上面的"新增"仍然要统计，
        # 因为凭空冒出标识符恰恰是这类题最该警惕的事）。
        if not diff.kept and not diff.lost:
            continue

        num_cases += 1
        total += len(diff.kept) + len(diff.lost)
        kept += len(diff.kept)
        lost += len(diff.lost)
        if diff.lost:
            cases_with_loss += 1

    return IdentifierSummary(
        num_cases_with_identifier=num_cases,
        num_identifiers=total,
        num_kept=kept,
        num_lost=lost,
        # total 为 0 时返回 1.0 而不是 0.0：一个标识符都没有，谈不上"丢失"，
        # 报 0.0 会被误读成"全丢了"。
        retention=kept / total if total else 1.0,
        num_cases_with_loss=cases_with_loss,
        num_cases_with_introduced=cases_with_introduced,
    )
