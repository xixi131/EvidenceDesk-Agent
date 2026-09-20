"""容错 JSON 读取的单元测试。

真实事故：run 文件被编辑器「保存时自动格式化」拍成了缩进版 JSON，
内容一个字没丢，但按行 json.loads 的读法当场炸掉，一份花了 60 次 LLM
调用的结果差点报废。这些测试就是钉死「两种排版都得能读」。
"""

import pytest

from evidence_desk.evaluation.jsonl import iter_json_objects


def test_reads_standard_jsonl() -> None:
    text = '{"id": "a"}\n{"id": "b"}\n'

    assert [o["id"] for o in iter_json_objects(text)] == ["a", "b"]


def test_reads_pretty_printed_objects() -> None:
    """被格式化成缩进版也要能读——这就是当初炸掉的那种文件。"""

    text = '{\n  "id": "a"\n}\n{\n  "id": "b"\n}\n'

    assert [o["id"] for o in iter_json_objects(text)] == ["a", "b"]


def test_ignores_blank_lines_and_trailing_whitespace() -> None:
    text = '\n\n{"id": "a"}\n\n\n{"id": "b"}\n\n  '

    assert [o["id"] for o in iter_json_objects(text)] == ["a", "b"]


def test_empty_text_yields_nothing() -> None:
    assert list(iter_json_objects("   \n\n")) == []


def test_non_object_json_is_rejected() -> None:
    """只接受对象。读到数组/数字说明文件不是我们写的那种，早点炸比算出错数字好。"""

    with pytest.raises(ValueError, match="期望 JSON 对象"):
        list(iter_json_objects("[1, 2, 3]"))
