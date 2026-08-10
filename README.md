# 🎓 校园信息查询 Agent（郑州大学北校区）

基于 **RAG（检索增强生成）** 架构的校园信息智能问答系统。用户用自然语言提问，Agent 通过**多工具自主推理**（时间感知、知识库检索、网络搜索降级），基于真实数据生成**可溯源**的回答。已上线 **Android App（ZZUN-Agent）**，支持学生上传课表。

## 📲 Android App 下载（ZZUN-Agent）

**面向郑州大学北校区同学的内测版 App**，支持 Android 8.0+（64位）：

> **下载地址：http://120.26.244.59/download**

功能：
- 聊天问答：校历、校医院、食堂、快递、图书馆等校园信息
- 上传课表：上传后可查课程、老师相关问题
- 查看教程：内置课表获取视频教程

> ⚠️ 安装需允许"未知来源应用"。当前为内测版本，如有问题请联系管理员 QQ：1304821679

## ✨ 核心亮点

- **ReAct 多工具 Agent**：Agent 自主决定动作——`TIME`（获取当前时间）、`SEARCH`（检索知识库）、`WEB_SEARCH`（网络搜索降级），发现信息不足会主动补查
- **时间感知推理**：问"现在开门吗"，Agent 先获取当前日期，再结合"正常学期/暑假"不同值班表判断，不凭记忆瞎答
- **信息可溯源**：每次回答附带 `信息来源 + 信息更新时间`，杜绝大模型幻觉
- **智能降级链路**：知识库查不到 → 明确提示"信息库未收录" → 自动转网络搜索（附带校园关键词）
- **课表众包机制**：学生上传 docx 课表 → 自动解析课程/老师 → 按班级去重入库，知识库可持续生长

## 🛠️ 技术栈

| 组件 | 用途 |
|------|------|
| Python 3.10 | 主语言 |
| FastAPI | Web 框架（RESTful API） |
| DeepSeek API | 大模型推理（ReAct 循环） |
| 自研检索引擎 | 中文分词 + TF-IDF 打分，零外部依赖 |
| python-docx | 课表 docx 解析 |
| Kivy | Android 客户端 |
| GitHub Actions | 自动打包 APK |

## 📁 项目结构

```
campus_agent/
├── main.py              # FastAPI 入口（/api/query、/api/health、/api/upload-schedule）
├── agent.py             # ReAct Agent 核心（TIME/SEARCH/WEB_SEARCH 工具循环）
├── db.py                # 知识库检索引擎 + 课表入库（按班级去重）
├── android/             # Kivy Android 客户端（聊天界面 + 上传课表）
│   └── chat_app.py
├── data/                # 知识库文档（校历/作息/校医院/餐饮/快递）
└── scripts/
    ├── import_docs.py   # 文档导入
    └── parse_schedule.py # 课表 docx → 课程/老师解析
```

## 🧠 工作原理

```
用户提问
  ↓
ReAct Agent 循环（agent.py）
  ├─ TIME?        获取当前日期（时间相关问题）
  ├─ SEARCH?      检索知识库 → 观察结果
  ├─ 信息不足 → 继续检索 / 降级 WEB_SEARCH（网络搜索）
  └─ FINAL        基于真实数据生成回答
  ↓
返回 answer + 信息来源 + 更新时间
```

**为什么用 RAG 而不是直接问大模型？** 大模型会"幻觉"编造答案。RAG 先检索到真实文档，再让模型照着文档回答——答案有据可依，可溯源。本项目更进一步：**Agent 化**（自主多轮检索）+ **时间感知**（区分学期/假期）+ **降级兜底**（网络搜索）。

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install fastapi uvicorn requests python-docx
```

### 2. 配置 DeepSeek API Key
```bash
export DEEPSEEK_API_KEY="sk-你的key"   # Linux/macOS
setx DEEPSEEK_API_KEY "sk-你的key"     # Windows
```

### 3. 导入知识库 + 启动服务
```bash
python scripts/import_docs.py
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 测试
```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "现在是暑假，校医院口腔科什么时候开？"}'
```

示例响应：
```json
{
  "answer": "今天是2026年8月6日（星期三），处于暑假期间（校历：7月26日-9月5日）。暑假值班表中口腔科（102室）周一至周五值班，今天周三可前往。",
  "sources": ["校历.txt", "校医院-暑假值班表.txt"]
}
```

### 5. 学生上传课表（众包）
```bash
curl -X POST http://127.0.0.1:8000/api/upload-schedule \
  -F "file=@我的课表.docx"
```

## 📊 已收录知识

| 类别 | 内容 |
|------|------|
| 校历 | 2025-2026 / 2026-2027 双学年 |
| 课表 | 课程、教室、任课老师（众包入库） |
| 校医院 | 正常学期 + 暑假双值班表（含科室房号） |
| 餐饮/作息/快递/校门 | 日常校园信息 |

## 🗂️ 后续规划

- [ ] 接入本地 Ollama 模型（零 API 成本）
- [ ] 查询缓存（相同问题不重复调 API）
- [ ] 多轮对话上下文记忆

## 🔒 隐私与安全

- **课表上传仅提取课程/老师**：学生上传的 docx 不保存原件，仅解析出"班级 + 课程 + 任课老师"入库，**不存储个人姓名**
- **上传即告知**：上传成功后会提示"仅提取课程与任课老师信息用于查询"
- **数据目录权限**：部署到服务器后，请确保 `data/` 目录仅服务账户可写：
  ```bash
  chmod 750 data/ && chown www-data:www-data data/
  ```
- **API Key 安全**：DeepSeek API Key 通过环境变量配置，绝不出现在代码仓库中
