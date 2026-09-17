"""中文分词：把文本切成空格分隔的词串，供 BM25 关键词检索使用（P6-03）。

为什么需要这个模块
------------------
BM25 的匹配是 token **精确相等**，不是模糊比较。英文靠空格切词，文档端和
查询端切出来的天然一致；中文没有空格，得靠词典去猜词边界，而"猜"是上下文
相关的——同样是「标签」这两个字，在文档里可能跟前后字粘成别的词，在查询里
单独出现又是另一个词。两边 token 不相等，BM25 就**直接返回 0 条**（不是排
序靠后）。这正是上一版用 Weaviate 内置 GSE_CH 分词器时翻车的原因。

解法：把分词这一步从数据库里拿回来自己做。索引时和查询时都调用下面这同一个
`segment()`，Weaviate 那边的 `content_tokens` / `title_tokens` 字段只用
WHITESPACE 分词（老老实实按空格切，不做任何"聪明"判断）。两端共用一个函数，
"失配"这一类 bug 就从结构上不可能发生了。

铁律
----
**索引和查询必须调用同一个 `segment()`。** 改 DOMAIN_WORDS、换 jieba 版本、
调整过滤规则，都等于换了一套 token——必须同步改 `TOKENIZER_VERSION` 并重建
索引，否则索引里存的和查询时切的会悄悄对不上，退回今天这个 bug。
"""

from functools import lru_cache

import jieba

# 分词方案的版本号。跟 Chunk 上的 chunk_config_version / cleaning_rules_version
# 是同一个思路：凡是会改变"索引里到底存了什么"的配置，都要有版本号可追溯。
# 这个值会随每个 Chunk 一起写进 Weaviate（见 KnowledgeChunkIndexer），
# 方便随时确认"索引是用哪一版分词建的"。
TOKENIZER_VERSION = "jieba-0.42.1-domain-v1"

# 领域自定义词典：jieba 的通用词典不认识的 GitHub Actions 术语。
#
# ⚠️ 这里**只收原子词，绝不收长复合词**，这是个反直觉但很关键的约束。
#
# 原因：jieba 是最大匹配式的，词典里有什么长词，它就会优先切出那个长词。
# 如果把「自托管运行器」也加进词典，文档会被切成一个整 token
# `自托管运行器`，而用户查「自托管」时切出来的是 `自托管`——两者不相等，
# 又是 0 命中，等于把我们正在修的 bug 原样重新引入一遍。
#
# 反过来，只收原子词的话，长词会由原子词**自动组合**出来：
#   「自托管运行器」-> ['自托管', '运行器']   查「自托管」命中 ✅
#   「工作流文件」  -> ['工作流', '文件']     查「工作流」命中 ✅
# 组合是帮我们的，长词是坑我们的。
#
# 判断要不要收的标准：jieba 默认把它切碎后，碎片是否失去了意义。
#   收：「工作流」->['工作','流']，「流」单独没意义
#   不收：「矩阵策略」->['矩阵','策略']，两个碎片都还是有意义的词，
#         而且查询端会切出一模一样的两片，照样能匹配上
DOMAIN_WORDS = (
    "工作流",
    "运行器",
    "运行程序",
    "自托管",
    "依赖项",
    "检查项",
    "容器化",
)


@lru_cache(maxsize=1)
def _get_tokenizer() -> jieba.Tokenizer:
    """返回加载好领域词典的 jieba 分词器（全进程只建一次）。

    为什么要单独建 Tokenizer 实例，而不用 jieba.lcut() 这个模块级函数：
    模块级函数用的是 jieba 内部的全局分词器，一旦有别的代码也往里 add_word，
    我们的分词结果就会被悄悄改掉——而分词结果一变，索引就对不上了。自己持有
    一个实例，切分行为就完全由这个模块说了算。

    @lru_cache(maxsize=1)：给无参函数加缓存，等价于"只有第一次真正执行函数体，
    之后每次调用都直接返回第一次算出来的那个对象"——也就是一个写法更简洁的
    单例。jieba 首次切词要加载几十 MB 的词典（约 0.2 秒），不做缓存的话每次
    调用 segment() 都得重新加载一遍。
    """

    tokenizer = jieba.Tokenizer()
    for word in DOMAIN_WORDS:
        tokenizer.add_word(word)
    return tokenizer


def _is_meaningful(token: str) -> bool:
    """丢掉纯标点/纯空白的 token，只保留至少含一个字母数字或汉字的。

    jieba 会把标点也当成独立 token 吐出来，比如
    「分支、标签和/或路径」-> ['分支', '、', '标签', '和', '/', '或', '路径']。
    这些 '、' '/' 进倒排索引纯属噪音（几乎每篇文档都有，IDF 接近 0，还占空间）。

    用 isalnum() 判断：汉字 '标'.isalnum() 是 True，标点 '、'.isalnum() 是
    False。只要 token 里有任意一个字符是字母/数字/汉字就保留。
    """

    return any(char.isalnum() for char in token)


def segment(text: str) -> str:
    """把中文文本切成空格分隔的词串。

    索引端（KnowledgeChunkIndexer）和查询端（WeaviateBM25Retriever /
    WeaviateHybridRetriever）都必须调这个函数，不能各切各的。

    统一转小写是因为 Weaviate 的 WHITESPACE 分词**不会**帮忙做大小写归一
    （这正是我们选它的原因——它什么都不做）。所以大小写只能在这里处理：
    两端都转小写，查 "Actions" 才能命中文档里的 "actions"。

    >>> segment("配置自托管运行器")
    '配置 自托管 运行器'
    """

    tokens = _get_tokenizer().lcut(text.lower())
    return " ".join(token for token in tokens if _is_meaningful(token))
