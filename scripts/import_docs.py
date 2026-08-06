# -*- coding: utf-8 -*-
"""
文档导入模块
============
提供 bulk_import() 函数：从 data/ 目录导入所有文档到知识库。
在导入前自动清空已有文档。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import add_documents, get_stats, reset

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CHUNK_SIZE = 500
OVERLAP = 50


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) <= chunk_size:
            current += ("\n\n" + para) if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > chunk_size:
                # 超长段落：按行边界切成多个块，保证不劈断任何一行
                chunks.extend(_split_long_by_line(para, chunk_size, overlap))
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)
    return chunks


def split_by_sections(text, chunk_size=1200):
    """
    按 Markdown 标题（## 或 #）切分文档，每个小节独立成块。
    用于校历等"每节一个独立主题"的文件，保证检索时整节完整。
    """
    lines = text.split("\n")
    sections = []
    current_title = ""
    current_lines = []

    def flush():
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title + "\n" + body).strip())

    for line in lines:
        if line.strip().startswith(("#", "##", "###")):
            flush()
            current_title = line.strip()
            current_lines = [line.strip()]
        else:
            if current_lines:
                current_lines.append(line)
    flush()

    # 长小节再按行切分（防单节超长）
    chunks = []
    for sec in sections:
        if len(sec) <= chunk_size:
            chunks.append(sec)
        else:
            chunks.extend(_split_long_by_line(sec, chunk_size, OVERLAP))
    return chunks


def _split_long_by_line(text, chunk_size, overlap):
    """
    将超长段落按行边界切成块：每块凑够 chunk_size 就收尾，
    但切点对齐到换行符，保证行内容完整。
    """
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(current) + len(line) + 1 > chunk_size and current:
            chunks.append(current)
            # 保留末尾一行作为 overlap，减少上下文断裂
            tail = current.split("\n")[-1] if overlap > 0 else ""
            current = tail + "\n" if tail else ""
        current += ("\n" + line) if current and not current.endswith("\n") else line
        # 单行就超过 chunk_size：单独成块
        if len(current) > chunk_size:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def import_all():
    """递归扫描 data/ 目录，导入所有文档。先清空再导入。"""
    reset()
    
    # 递归收集所有 txt/md 文件，记录相对路径
    files = []
    for root, dirs, fnames in os.walk(DATA_DIR):
        for fname in fnames:
            if fname.endswith((".txt", ".md")):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, DATA_DIR)
                files.append((full, rel))
    
    if not files:
        print("No .txt or .md files found in data/")
        return

    total_chunks = 0
    for filepath, rel in files:
        text = read_file(filepath)

        # 校历类文件：按 ## 小节语义分块（每学期/假期独立一块）
        if "校历" in rel:
            chunks = split_by_sections(text)
        else:
            chunks = split_text(text)

        if not chunks:
            print("  %s - empty, skipped" % rel)
            continue

        metadatas = [{"source": rel}] * len(chunks)
        add_documents(chunks, metadatas)
        total_chunks += len(chunks)
        print("  OK %s - %d chunks imported" % (rel, len(chunks)))

    print("\nTotal: %d files, %d chunks" % (len(files), total_chunks))
    stats = get_stats()
    print("Stats: %d docs, %d vocab tokens" % (stats["doc_count"], stats["vocab_size"]))


if __name__ == "__main__":
    import_all()
