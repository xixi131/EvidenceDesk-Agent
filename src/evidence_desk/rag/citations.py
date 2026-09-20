"""把回答里的引用标号解析出来，并组装成引用列表。

## 为什么改成这样（P6-06）

改造前：``build_citations(hits)`` 只看检索结果，把捞回来的 chunk 按父文档去重后
**全部**列成"来源"——它根本不看回答文本。于是：

- 回答正文里没有任何 ``[n]`` 标号，用户无法知道哪句话来自哪篇资料；
- 来源列表里混着回答压根没用到的资料。

好比写论文正文一个脚注不打，最后附一份"我去图书馆借过的所有书"。
那不是引用，是借书记录——没法核实，也没法评测。

改造后：模型在每个事实句末尾标 ``[n]``，这里把标号解析出来，
**只为被真正引用的资料生成引用**。箭头方向反过来了：
从"检索到什么就引什么"变成"**答案用了什么才引什么**"。

## 编号规则：沿用资料编号，不重排、不去重

``[n]`` 里的 n 指的是提示词里的"资料n"，也就是 ``hits[n-1]``。
所以引用的 index 必须**原样沿用这个编号**：

- **不重新编号**：重排会让答案里的 ``[3]`` 和来源列表里的 ``[3]`` 指向不同文档。
  代价是编号可能不连续（1、3、4）——学术引用本来就这样，
  连续好看 vs 指向正确，后者压倒性重要。
- **不按父文档去重**：去重一旦丢掉资料3，模型写的 ``[3]`` 就成了悬空标号。
  去重和标号可解析二者不可兼得，必须保后者。
"""

import re

from evidence_desk.rag.models import Citation, RetrievalHit

# 回答正文里的引用标号，形如 [1]、[3]。括号里的 \d+ 是捕获组，
# findall 只会把括号内的数字交出来，不用再自己剥方括号。
_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


def parse_citation_markers(text: str) -> list[int]:
    """从回答正文里抽出所有引用标号，去重后按数字升序返回。

    这个函数**只负责"文本里写了哪些标号"，不判断这些标号合不合法**。
    模型完全可能标出 [7] 而参考资料只有 5 条——那是越界引用，
    是 Citation Correctness 要测的失败模式之一。如果在这里顺手过滤掉，
    上层指标就永远看不到这个错误，报告会显示一片完美。

    判断合法是调用方的事，这里只做忠实的提取。
    """

    return sorted({int(marker) for marker in _MARKER_PATTERN.findall(text)})


def build_citations(
    hits: list[RetrievalHit], cited_indices: list[int]
) -> list[Citation]:
    """只为答案真正引用到的资料生成引用，index 沿用资料编号。

    越界的标号（比如只有 5 条资料却标了 [7]）在这里被跳过——造不出不存在的
    引用。但这**不是**在修复错误：原始标号由 parse_citation_markers 保留，
    指标那边照样能统计出越界率。生产侧只是不让它崩，评测侧照样看得见。
    """

    citations: list[Citation] = []
    for index in sorted(set(cited_indices)):
        # 资料编号从 1 开始（给人看的），列表下标从 0 开始（给机器看的），
        # 所以这里要 -1。越界的直接跳过。
        if not 1 <= index <= len(hits):
            continue
        hit = hits[index - 1]
        citations.append(
            Citation(
                index=index,
                chunk_id=hit.chunk_id,
                parent_doc_id=hit.parent_doc_id,
                title=hit.title,
                section_path=hit.section_path,
                source_url=hit.source_url,
            )
        )

    return citations
