# -*- coding: utf-8 -*-
from __future__ import annotations
"""
知识库检索模块
===============
MVP 阶段：使用纯 Python 关键词检索（TF-IDF 风格），零模型依赖。
API 保持不变（add_documents / search），将来切换到 ChromaDB 向量检索只需替换本文件。

使用方式：
    from db import add_documents, search, get_stats
"""

import os
import re
from collections import Counter
from math import log

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_MODULE_DIR, "data")
INDEX_FILE = os.path.join(_MODULE_DIR, "index.json")

# 内存存储（MVP 阶段不用 ChromaDB）
_documents: list[dict] = []  # [{"content": str, "metadata": dict, "tokens": set}, ...]
_idf: dict[str, float] = {}   # token -> idf 值


def _tokenize(text: str) -> set[str]:
    """简单中文分词：按标点/空格切 + 提取2-4字词组"""
    text = re.sub(r"[^\u4e00-\u9fff\w]", " ", text.lower())
    words = set()
    chars_only = re.sub(r"\s+", "", re.sub(r"[^\u4e00-\u9fff]", "", text))
    # 单字
    for c in chars_only:
        words.add(c)
    # 2-4字词组
    for length in [2, 3, 4]:
        for i in range(len(chars_only) - length + 1):
            words.add(chars_only[i:i + length])
    # 英文/数字 token
    for token in re.findall(r"[a-z0-9]+", text):
        words.add(token)
    return words


def _rebuild_index():
    """重建 IDF 索引"""
    global _idf
    N = len(_documents)
    if N == 0:
        _idf = {}
        return
    df = Counter()
    for doc in _documents:
        for token in doc["tokens"]:
            df[token] += 1
    _idf = {token: log((N + 1) / (df[token] + 1)) + 1 for token in df}


def _save():
    """持久化到 JSON 文件"""
    import json
    data = {
        "documents": [{"content": d["content"], "metadata": d["metadata"]} for d in _documents],
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load():
    """从 JSON 文件恢复"""
    import json
    global _documents, _idf
    
    # 调试日志
    with open(os.path.join(_MODULE_DIR, "db_debug.txt"), "a", encoding="utf-8") as dlog:
        dlog.write(f"_load() called\n")
        dlog.write(f"  INDEX_FILE: {INDEX_FILE}\n")
        dlog.write(f"  exists: {os.path.exists(INDEX_FILE)}\n")
        dlog.write(f"  cwd: {os.getcwd()}\n")
    
    if not os.path.exists(INDEX_FILE):
        return
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _documents = []
    for d in data["documents"]:
        _documents.append({
            "content": d["content"],
            "metadata": d.get("metadata", {}),
            "tokens": _tokenize(d["content"]),
        })
    _rebuild_index()


def add_documents(documents: list[str], metadatas: list[dict] | None = None):
    """将文档存入知识库"""
    if metadatas is None:
        metadatas = [{}] * len(documents)
    
    for content, meta in zip(documents, metadatas):
        tokens = _tokenize(content)
        _documents.append({"content": content, "metadata": meta, "tokens": tokens})
    
    _rebuild_index()
    _save()
    return len(documents)


def _truncate_by_line(text: str, max_len: int = 800) -> str:
    """
    按行边界截断文本：保证截断处在一行的结尾，不切断半行。
    若文本本身短于 max_len，原样返回。
    """
    if len(text) <= max_len:
        return text
    # 从 max_len 往前找最近的换行符，在行边界截断
    cut = text.rfind("\n", 0, max_len)
    if cut == -1:
        # 没有换行符，硬截断
        return text[:max_len]
    return text[:cut]


def search(query: str, top_k: int = 3) -> list[dict]:
    """检索与 query 最相关的文档"""
    global _documents
    if not _documents:
        _load()
    if not _documents:
        return []
    
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    
    scores = []
    for i, doc in enumerate(_documents):
        overlap = query_tokens & doc["tokens"]
        if not overlap:
            continue
        score = sum(_idf.get(t, 1.0) for t in overlap)
        scores.append((score, i))
    
    scores.sort(reverse=True)
    results = []
    for score, idx in scores[:top_k]:
        results.append({
            "content": _truncate_by_line(_documents[idx]["content"], 800),  # 按行边界截断
            "metadata": _documents[idx]["metadata"],
            "score": round(score, 2),
        })
    
    # 如果关键词匹配不到，退回全文搜索
    if not results:
        for i, doc in enumerate(_documents):
            if query.lower() in doc["content"].lower():
                results.append({
                    "content": doc["content"][:500],
                    "metadata": doc["metadata"],
                    "score": 0.5,
                })
                if len(results) >= top_k:
                    break
    
    return results


def get_stats() -> dict:
    """知识库统计"""
    return {
        "doc_count": len(_documents),
        "vocab_size": len(_idf),
    }


def add_schedule(student: dict, courses: list[dict]) -> str:
    """
    将解析出的课表写入知识库（按班级去重）。
    返回状态信息。
    """
    class_name = student.get("class", "") or "未知班级"
    filename = f"课表-{class_name}.txt"
    filepath = os.path.join(DATA_DIR, filename)

    # 已存在：班级课表已收录
    if os.path.exists(filepath):
        return f"该班级（{class_name}）的课表已收录，无需重复上传。"

    # 生成课表文本（不存储个人姓名，保护隐私）
    lines = [
        f"# {class_name} 课表",
        f"# 年级：{student.get('grade', '')} | 专业：{student.get('major', '')}",
        f"# 来源：学生上传 | 采集时间：{_today()}",
        "",
    ]
    for c in courses:
        detail = f"- {c['course']}：{c['teacher']}"
        parts = []
        if c.get("period"):
            parts.append(f"第{c['period']}节")
        if c.get("room"):
            parts.append(c["room"])
        if c.get("week"):
            parts.append(f"（{c['week']}）")
        if parts:
            detail += " " + " ".join(parts)
        lines.append(detail)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 重新导入知识库（包含新文件）
    import subprocess, sys
    script = os.path.join(_MODULE_DIR, "scripts", "import_docs.py")
    subprocess.run([sys.executable, script], check=True, capture_output=True)

    return f"已收录 {class_name} 的课表，共 {len(courses)} 门课程。"


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def reset():
    """清空知识库（重新导入前调用）"""
    global _documents, _idf
    _documents = []
    _idf = {}
    if os.path.exists(INDEX_FILE):
        os.remove(INDEX_FILE)


# 向后兼容 ChromaDB 风格的接口
def get_collection():
    """兼容旧 API（无操作）"""
    pass


# 启动时自动加载
_load()
