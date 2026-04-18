"""
清理 yixue_knowledge.json：
1. 删除 sections.__intro__（与 content 重复）
2. 去除文本中多余的空格（中文词语之间被爬虫插入的空格）
"""
import json
import re

INPUT  = "yixue_knowledge.json"
OUTPUT = "yixue_knowledge.json"  # 原地覆盖，如需备份改此路径


def clean_spaces(text: str) -> str:
    """去除中文语境下多余的空格，保留英文/数字间合理空格。"""
    if not isinstance(text, str):
        return text
    # 中文字符/标点 与任意字符之间的空格，直接删掉
    # 规则：空格两侧至少有一侧是中文字符/中文标点，则删除该空格
    cjk = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
    # 中文后跟空格
    text = re.sub(rf'({cjk}) +', r'\1', text)
    # 空格后跟中文
    text = re.sub(rf' +({cjk})', r'\1', text)
    # 合并连续多个空格为一个（处理英文段落）
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def clean_value(obj):
    """递归处理 JSON 中所有字符串值。"""
    if isinstance(obj, str):
        return clean_spaces(obj)
    if isinstance(obj, list):
        return [clean_value(v) for v in obj]
    if isinstance(obj, dict):
        return {k: clean_value(v) for k, v in obj.items()}
    return obj


def process(data: dict) -> dict:
    pages = data.get("pages", {})
    for key, page in pages.items():
        # 1. 删除 sections.__intro__（与 content 重复）
        sections = page.get("sections", {})
        if "__intro__" in sections:
            del sections["__intro__"]

        # 2. 清理所有文本空格
        pages[key] = clean_value(page)

    data["pages"] = pages
    return data


if __name__ == "__main__":
    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    data = process(data)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ 处理完成 →", OUTPUT)
