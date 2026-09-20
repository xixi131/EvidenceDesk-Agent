"""容错的 JSON 记录读取：一行一条，或被格式化成缩进版，都能读。

为什么需要这个：run 文件和 judge 判定文件都是 JSONL（一行一条）。但这种文件
很容易被编辑器的"保存时自动格式化"拍成缩进版 JSON——内容一个字没丢，
只是换行位置变了，而按行 json.loads 的读法会当场炸掉：

    JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2

一份跑了几分钟、花了几十次 LLM 调用的结果，因为被编辑器碰了一下就读不出来，
这是不可接受的。与其要求所有人都别用格式化，不如让读取端两种都认。

做法：不按行切，改用 json.JSONDecoder().raw_decode 从文本里**连续**解析
JSON 对象——它每次从给定位置解析出一个完整对象，并告诉你结束位置，
从那儿继续解析下一个。一行一条也好、缩进版也好，对它都一样。
"""

import json
from collections.abc import Iterator

_DECODER = json.JSONDecoder()


def iter_json_objects(text: str) -> Iterator[dict[str, object]]:
    """从一段文本里依次解析出所有 JSON 对象。

    兼容两种排版：
        {"a": 1}\n{"a": 2}        一行一条（标准 JSONL）
        {\n  "a": 1\n}\n{\n ...   被格式化成缩进版
    """

    index = 0
    length = len(text)
    while index < length:
        # 跳过对象之间的空白（换行、缩进、文件末尾的空行）。
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            return
        obj, end = _DECODER.raw_decode(text, index)
        if not isinstance(obj, dict):
            raise ValueError(f"期望 JSON 对象，实际读到 {type(obj).__name__}。")
        yield obj
        index = end
