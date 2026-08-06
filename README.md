# 校园信息查询 Agent 🎓

一个基于 **RAG（检索增强生成）** 架构的校园信息问答系统。用户用自然语言提问，Agent 自主检索知识库、结合大模型生成基于真实数据的回答——不凭空编造。

## ✨ 功能亮点

- **自然语言问答**：问"RFID 几点上课？"直接得到准确回答
- **ReAct 多轮检索**：Agent 自主决定检索动作，发现信息不足会主动补查（如先查课表再查作息表换算成具体钟点）
- **信息可溯源**：回答附带知识库来源，可信可查
- **知识库可扩展**：往 `data/` 放 txt/md 文件即可扩展，零代码改动

## 🛠️ 技术栈

| 组件 | 用途 |
|------|------|
| Python 3.10 | 主语言 |
| FastAPI | Web 框架，提供 HTTP 接口 |
| DeepSeek API | 大模型生成回答（ReAct 推理） |
| 自研检索引擎 | 中文分词 + TF-IDF 打分，零外部依赖 |
| python-docx | 解析学生课表 docx |

## 📁 项目结构

```
campus_agent/
├── main.py              # FastAPI 入口（/api/query、/api/health）
├── agent.py             # ReAct Agent 核心（SEARCH/FINAL 循环）
├── db.py                # 知识库检索引擎（分词 + 打分）
├── index.json           # 知识库索引（程序自动生成）
├── data/                # 知识库文档（放 txt/md 即可扩展）
│   ├── 校历.txt
│   ├── 课表.txt
│   ├── 校园设施.txt      # 校医院值班、校门、快递
│   ├── 校医院-暑假值班表.txt
│   ├── 餐饮.txt
│   └── 作息时间表.txt
└── scripts/
    ├── import_docs.py   # 文档导入（data/ → index.json）
    └── parse_schedule.py # 课表 docx → 课程/老师解析
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn requests python-docx
```

### 2. 配置 DeepSeek API Key

```bash
# Windows 用户级环境变量
setx DEEPSEEK_API_KEY "sk-你的key"
# 或直接设置环境变量
export DEEPSEEK_API_KEY="sk-你的key"
```

### 3. 导入知识库

```bash
python scripts/import_docs.py
```

### 4. 启动服务

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 5. 测试

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "RFID原理及应用几点上课？"}'
```

示例响应：

```json
{
  "answer": "RFID原理及应用在周一第1-2节上课，时间为8:00-9:40，地点在北区9_102。",
  "sources": ["课表.txt", "作息时间表.txt"]
}
```

## 🔄 更新知识库

1. 编辑 `data/` 下的文件或新增 txt/md
2. 重新运行 `python scripts/import_docs.py`
3. 完成——新内容立即生效

## 🧠 工作原理

```
用户提问
  ↓
ReAct Agent 循环（agent.py）
  ├─ SEARCH: 检索知识库 → 观察结果
  ├─ 信息不足？→ 继续 SEARCH 补充
  └─ 信息足够 → FINAL: 生成回答
  ↓
返回 answer + sources
```

**为什么用 RAG 而不是直接问大模型？** 大模型会"幻觉"编造答案。RAG 先检索到真实文档，再让模型照着文档回答——答案有据可依，可溯源。

## 📊 知识库内容

| 类别 | 内容 |
|------|------|
| 校历 | 学年安排、假期 |
| 课表 | 课程时间、教室、任课老师 |
| 校园设施 | 校医院值班表（正常学期+暑假）、校门、快递站 |
| 餐饮 | 南/北餐厅营业时间 |
| 作息时间表 | 节次 ↔ 具体钟点换算 |

## 📌 待办 / 可扩展方向

- [ ] 课表上传接口（同学上传 docx 自动解析，众包老师信息）
- [ ] 接入本地 Ollama 模型（零 API 成本）
- [ ] 查询缓存（相同问题不重复调 API）
