"""
校园信息查询 Agent — FastAPI 入口
===================================
v0.2 — RAG 链路已接入（检索 + DeepSeek 生成）

运行方式（在 campus_agent 目录下）：
    D:\mocha_workbench\FASTAPI_PRACTICE\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations
from db import get_stats, add_schedule
from agent import agent_query
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import os

app = FastAPI(title="校园信息查询 Agent", version="0.3.0")


@app.on_event("startup")
async def startup():
    """应用启动时确保知识库已加载"""
    s = get_stats()
    print(f"[startup] 知识库状态: {s['doc_count']} 文档, {s['vocab_size']} 词")


# ---------- 请求体 ----------
class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []


# ---------- 端点 ----------
@app.get("/api/health")
async def health():
    s = get_stats()
    return {
        "status": "ok", "version": "0.2.0",
        "kb_docs": s["doc_count"],
        "kb_tokens": s["vocab_size"],
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    # Step 0: 输入校验
    question = req.question.strip()
    if not question:
        return QueryResponse(answer="请输入有效的问题。", sources=[])
    if len(question) > 500:
        return QueryResponse(answer="问题太长了，请简化后再问。", sources=[])

    # Step 1: 交给 ReAct Agent 处理（自主多轮检索 + 生成）
    answer, sources = agent_query(question)

    # Step 2: 返回回答 + 来源
    return QueryResponse(
        answer=answer,
        sources=sources,
    )


@app.post("/api/upload-schedule")
async def upload_schedule(file: UploadFile = File(...)):
    """接收学生课表 docx，解析并按班级去重入库"""
    import tempfile
    import shutil

    if not file.filename.endswith(".docx"):
        return {"success": False, "message": "请上传 .docx 格式的课表文件。"}

    # 保存临时文件
    tmp_path = os.path.join(tempfile.gettempdir(), f"schedule_{file.filename}")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
        from parse_schedule import parse_schedule_file
        data = parse_schedule_file(tmp_path)
    except Exception as e:
        return {"success": False, "message": f"课表解析失败：{str(e)[:100]}"}
    finally:
        os.remove(tmp_path)

    if not data["courses"]:
        return {"success": False, "message": "未从课表中解析出课程信息，请确认文件是标准的学生课表。"}

    # 入库（按班级去重）
    message = add_schedule(data["student"], data["courses"])
    privacy_note = "说明：仅提取课程与任课老师信息用于查询，不存储个人姓名。"
    return {
        "success": True,
        "message": message + " " + privacy_note,
        "student": data["student"],
        "course_count": len(data["courses"]),
        "teachers": data["teachers"],
    }
