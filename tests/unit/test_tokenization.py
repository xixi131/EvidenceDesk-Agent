"""中文分词的单元测试（不依赖 Weaviate）。

这组测试守的是 P6-03 的核心不变量：**同一个词，在文档里和在查询里必须切出
一样的 token**。上一版用 Weaviate 内置 GSE_CH 分词器时正是这条被破坏了，
导致中文 BM25 直接 0 命中。
"""

from evidence_desk.rag.tokenization import DOMAIN_WORDS, segment

# 取自真实语料（data/knowledge_base/github_actions_zh_v1）的句子，配上用户可能
# 会拿来搜的词。「标签」「构件」「取消」就是当初 GSE_CH 查不到的那几个词。
DOC_AND_QUERY_CASES = [
    ("事件支持你自定义按分支、标签和/或路径进行筛选。", "标签"),
    ("分钟数，或下载日志和创建构件。", "构件"),
    ("的常规取消操作未按预期执行，可能是", "取消"),
    ("在包含工作流的仓库中设置机密或变量来启用", "机密"),
    ("在包含工作流的仓库中设置机密或变量来启用", "工作流"),
    ("配置自托管运行器来运行工作流作业", "自托管"),
    ("配置自托管运行器来运行工作流作业", "运行器"),
]


def test_query_tokens_are_subset_of_document_tokens() -> None:
    """回归测试：查询词切出来的 token 必须都能在文档 token 里找到。

    这正是 BM25 能否命中的充要条件——BM25 靠 token 精确相等匹配，只要查询端
    切出来的某个 token 在文档端不存在，这个词就贡献不了任何分数。

    这条断言如果挂了，说明分词的对称性被破坏了（多半是 DOMAIN_WORDS 里加了
    长复合词，或者索引端/查询端用了不同的切法），中文 BM25 会静默失效——
    不报错，只是查不到东西。
    """

    for document, query in DOC_AND_QUERY_CASES:
        doc_tokens = set(segment(document).split())
        query_tokens = segment(query).split()

        assert query_tokens, f"查询词「{query}」被切没了"
        missing = [token for token in query_tokens if token not in doc_tokens]
        assert not missing, (
            f"查询「{query}」切出的 {missing} 不在文档 token {sorted(doc_tokens)} 里，"
            f"BM25 将无法命中这篇文档"
        )


def test_domain_words_are_not_split() -> None:
    """自定义词典里的词必须整个保留，不能被切碎。"""

    for word in DOMAIN_WORDS:
        assert segment(word) == word, f"领域词「{word}」被切碎了"


def test_compound_words_split_into_domain_words() -> None:
    """长复合词要由原子词组合出来，而不是自成一个整 token。

    这条是 DOMAIN_WORDS「只收原子词」那条约束的守门测试。假如有人往词典里
    加了「自托管运行器」，这里就会切出单个 token `自托管运行器`，用户查
    「自托管」时就再也命中不了——等于把 GSE_CH 那个 bug 重新引入一遍。
    """

    assert segment("自托管运行器") == "自托管 运行器"
    assert segment("工作流文件") == "工作流 文件"


def test_case_is_normalised() -> None:
    """大小写必须在这里归一：Weaviate 的 WHITESPACE 分词不会代劳。"""

    assert segment("使用 Actions 和 GITHUB") == segment("使用 actions 和 github")
    assert "actions" in segment("配置 Actions 工作流").split()


def test_punctuation_is_dropped() -> None:
    """纯标点不进倒排索引：几乎每篇都有，区分度为零，只占空间。"""

    tokens = segment("分支、标签和/或路径。").split()
    assert "标签" in tokens
    assert "、" not in tokens
    assert "/" not in tokens


def test_latin_identifier_is_split_into_searchable_terms() -> None:
    """拉丁标识符会按标点拆成多个词——这是我们要的效果。

    `actions/upload-artifact` 拆成三个词后，用户不管搜完整标识符还是只搜
    `upload artifact`，都能匹配上，召回更稳。
    """

    tokens = segment("使用 actions/upload-artifact 上传").split()
    assert {"actions", "upload", "artifact"} <= set(tokens)


def test_empty_and_symbol_only_text() -> None:
    """空文本和纯标点都应该安全地切成空串，而不是抛异常。"""

    assert segment("") == ""
    assert segment("、。！/") == ""
