# -*- coding: utf-8 -*-
"""
ReAct Agent 核心模块
====================
让 LLM 自主决定检索动作：SEARCH 检索知识库 → 观察结果 → 再决定，
直到它有足够信息输出 FINAL 回答。

用法：
    from agent import agent_query
    answer, sources = agent_query("RFID原理及应用几点上课？")
"""

import os
import winreg
import requests
import re
from urllib.parse import quote

from db import search

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_STEPS = 7  # 最多循环轮数，防止死循环


def web_search(query: str, top_k: int = 5) -> str:
    """
    网络搜索（360搜索 so.com，无需 API key，国内可访问，结果针对中文站点）。
    自动附带"郑州大学北校区"关键词。
    返回格式化文本：标题 + 链接 + 摘要。
    """
    full_query = f'"郑州大学" 北校区 {query}'
    url = f"https://www.so.com/s?q={quote(full_query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"（网络搜索失败：{str(e)[:80]}）"

    html = resp.text
    # 360 结果：<li class="res-list"> 内含 <h3><a href>标题</a></h3> 和摘要 <p>
    results = []
    blocks = re.findall(r'<li class="res-list".*?</li>', html, re.DOTALL)
    for block in blocks[:top_k]:
        title_m = re.search(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        snip_m = re.search(r"<p[^>]*>(.*?)</p>", block, re.DOTALL)
        if title_m:
            link = title_m.group(1)
            title = re.sub(r"<[^>]+>", "", title_m.group(2)).strip()
            title = title.replace("&quot;", '"').replace("&amp;", "&")
            snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
            results.append(f"- {title}\n  {snippet}\n  {link}")

    if not results:
        return "（网络搜索无结果）"
    return "\n".join(results)

SYSTEM_PROMPT = """你是郑州大学北校区校园信息助手 Agent。你可以通过检索工具获取知识库信息来回答问题。

可用工具：
- TIME             — 获取当前日期。当问题涉及"今天/现在/什么时候去/是否开门"等时间相关判断时，先调用 TIME 知道今天是几号、星期几。
- SEARCH: <查询词>  — 在校园信息库中检索相关信息。可以多次调用，用不同的查询词。
- WEB_SEARCH: <查询词> — 在互联网上搜索相关信息（会自动附带"郑州大学北校区"关键词）。
- FINAL: <回答>     — 你已经获得足够信息，输出最终回答。

规则（必须严格遵守）：
1. 【强制】只有实际调用过 SEARCH 并看到检索结果后，才能输出 FINAL。禁止凭常识或记忆直接回答。
2. 如果问题与时间相关（如"几点开门""什么时候值班""现在开门吗"），先调用 TIME 获取当前日期。
3. 结合 TIME 得到的日期和 SEARCH 得到的知识库内容推理。例如：知识库中有"正常学期值班表"和"暑假值班表"，要根据当前日期判断该用哪一份。
4. 事实来源层级：学期时间（开学、放假、寒暑假起止日期）一律以【校历】的检索结果为准；值班表/营业时间文件标题中的日期范围只是该表适用期，不代表真实放假时间。问"是不是暑假""几号放假"先 SEARCH 校历。
   【多学年校历选择规则】信息库中可能同时有多个学年的校历（如2025-2026学年和2026-2027学年）。判断用哪个：用 TIME 获取当前日期，对比"当前正处于哪个学年的暑假/学期中"。
   - 问"什么时候开学/放假"（指即将到来的事件）时，优先采用**最新学年**（2026-2027学年）的秋季学期信息。
   - 问"现在是什么假期/现在在哪个学期"时，用当前日期判断所处学年的校历。
   - 回答时明确标注所用校历的学年（如"按2026-2027学年校历"）。
5. 如果第一次检索结果不够（比如只查到"第1-2节"但用户问的是"几点"，需要节次换算表），就继续 SEARCH 补充查询。
6. 降级触发条件（满足任一即调用 WEB_SEARCH）：
   a) SEARCH 返回"检索无结果"或内容明显不相关；
   b) 用户问的是最新/未来的具体信息（如"2026年""今年""新生报到"），但信息库只有旧数据（如2025-2026学年校历）；
   c) 信息库数据无法直接回答当前问题。
   触发降级时，先输出"信息库中未收录此信息，信息来源降级为网络搜索"，然后调用 WEB_SEARCH 到网络上搜索（会自动附带"郑州大学北校区"关键词），基于网络搜索结果回答，来源标注为"（信息来源：网络搜索）"。
7. 如果检索不到完全匹配的信息但有接近的可用数据，就基于最接近的可用检索结果回答，并明确说明该信息对应的年份/学期，不要反复检索同一内容或拒绝回答。例如库中只有2025-2026学年校历时，问"什么时候开学"应回答"按2025-2026学年校历，秋季学期9月8日开学"，并提示以学校最新通知为准。
8. 信息足够后，用 FINAL: 输出回答。
9. 回答要准确、简洁，基于检索到的校园信息库内容。
10. 检索结果中每份文档带有"采集时间"，回答末尾必须标注该时间。
11. 回答末尾**单独一行**（这一行内不要换行、不要加粗符号、不要用列表符号）标注来源，格式严格为：
    （信息来源：校园信息库 | 信息更新时间：<检索结果中的采集时间>）
    整行必须写在同一行内，来源和更新时间之间用" | "连接，不得换行拆开。
    如果信息来自网络搜索，则标注"（信息来源：网络搜索）"。
12. 【课表/老师问题专用】当用户问的是"某课程几点上/在哪个教室/哪个老师教"这类与具体课表或任课老师相关的问题，且 SEARCH 检索不到该用户的课表信息时：
    - 先说明"校园信息库中没有收录该班级的课表数据"；
    - 然后回复"请上传你的课表（docx 格式，可从本科生服务平台导出），我收录后才能回答你的课程问题"；
    - 不要用其他班级的课表猜测回答，不要降级到网络搜索（课表是个人数据，网上搜不到）。

示例：
用户: 校医院皮肤科现在开门吗？
助手: TIME
用户: [当前日期：2026-08-05，星期三]
助手: SEARCH: 皮肤科值班
用户: [检索结果: 正常学期皮肤科周二或周四上午；暑假值班表皮肤科（108室）周二、周四上午隔周，采集时间2026-07-13]
助手: SEARCH: 暑假放假时间
用户: [检索结果: 校历：暑假7月27日至9月6日，采集时间2026-08-04]
助手: FINAL: 今天是2026年8月5日（星期三），处于暑假期间（校历：7月27日至9月6日）。暑假值班表中皮肤科（108室）周二、周四上午隔周值班，今天是周三不值班。（信息来源：校园信息库 | 信息更新时间：2026-07-13）"""


def get_api_key() -> str:
    """获取 DeepSeek API key：环境变量 → Windows 用户级注册表"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")[0]
        except Exception:
            key = ""
    return key


def call_llm(messages: list[dict]) -> str:
    """调用 DeepSeek，返回助手回复内容"""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")

    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "temperature": 0.0},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_update_time(content: str) -> str:
    """从文档内容中提取采集时间，找不到返回空字符串"""
    import re
    m = re.search(r"采集时间[:：]\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})", content)
    if m:
        return m.group(1)
    m2 = re.search(r"([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})", content)
    return m2.group(1) if m2 else ""


def _format_results(results: list[dict]) -> str:
    """把检索结果格式化成给 LLM 看的文本"""
    if not results:
        return "（检索无结果）"
    parts = []
    for r in results:
        src = r["metadata"].get("source", "未知")
        uptime = _extract_update_time(r["content"])
        tag = f"，采集时间{uptime}" if uptime else ""
        parts.append(f"[来源:{src}{tag}]\n{r['content'][:600]}")
    return "\n---\n".join(parts)


def agent_query(question: str) -> tuple[str, list[str]]:
    """
    ReAct 循环主函数。
    返回 (最终回答, 使用的知识库来源列表)
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    used_sources: list[str] = []
    tool_used = False  # 是否执行过任何工具（TIME/SEARCH/WEB_SEARCH）
    searched = False   # 是否检索过知识库（SEARCH/WEB_SEARCH）——FINAL 的硬性要求
    time_checked = False  # 是否已获取过当前时间
    web_used = False  # 是否已执行过网络搜索
    # 时间相关问题关键词
    import re as _re
    TIME_KEYWORDS = ["几点", "什么时候", "现在", "开门", "关门", "放假", "开学", "值班", "营业", "今天", "时间", "几点开"]

    def _now_str():
        from datetime import datetime
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return (
            f"当前日期：{now.strftime('%Y年%m月%d日')}，"
            f"{weekdays[now.weekday()]}，"
            f"当前时间 {now.strftime('%H:%M')}"
        )

    def _run_search(query):
        """执行一次 SEARCH，返回结果文本"""
        nonlocal tool_used
        if not query:
            query = question
        results = search(query, top_k=4)
        tool_used = True
        # 校历优先级：若结果含多个学年的校历，最新学年(2026-2027)排最前，并提示 Agent
        latest_xiaoli = [r for r in results if "2026-2027" in r["metadata"].get("source", "")]
        other_xiaoli = [r for r in results if "校历" in r["metadata"].get("source", "") and "2026-2027" not in r["metadata"].get("source", "")]
        rest = [r for r in results if r not in latest_xiaoli and r not in other_xiaoli]
        ordered = latest_xiaoli + other_xiaoli + rest
        for r in ordered:
            src = r["metadata"].get("source", "")
            if src and src not in used_sources:
                used_sources.append(src)
        hint = ""
        if latest_xiaoli and other_xiaoli:
            hint = "\n【提示】检索到多个学年的校历，回答与开学/放假/学期相关的问题时，优先采用2026-2027学年（最新学年）的数据。\n"
        return f"检索结果：{hint}\n{_format_results(ordered)}"

    def _normalize_source_line(text):
        """把回答中的来源标注强制合并为一行，并放在回答末尾"""
        import re
        # 提取整个（信息来源...）标注，包括中间可能的换行
        m = re.search(r"（信息来源[^）]*）", text, re.DOTALL)
        if m:
            source = m.group(0)
            # 合并内部换行：多个空格/换行 → 单个空格
            source = re.sub(r"\s+", " ", source)
            # 从原文中移除原标注（含换行），再在末尾追加规范标注
            text = text.replace(m.group(0), "").rstrip()
            text = text + "\n" + source
        return text

    def _clean_answer(text):
        """清理回答：合并 LLM 硬插的单换行，保留段落和来源行"""
        import re
        text = text.replace("\r\n", "\n")
        # 先保护来源标注行（已被 normalize 处理，最后一行）
        # 合并正文中的单换行（双换行保留为段落）
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result.append("")  # 空行 = 段落分隔
            elif stripped.startswith("（信息来源"):
                result.append(stripped)  # 来源行原样保留
            else:
                result.append(stripped)
        # 重新拼装：非空行之间用空格连接（合并句子），空行保留为段落
        merged = []
        for line in result:
            if line == "":
                merged.append("\n")
            else:
                merged.append(line)
        text = "".join(merged)
        # 把段落分隔 \n\n 还原；多余连续空行压缩
        text = re.sub(r"\n{2,}", "\n\n", text)
        return text.strip()

    for step in range(MAX_STEPS):
        # 强制时间注入：问题含时间词且尚未获取时间时，先给 LLM 当前时间
        # 注意：TIME 不算"检索过知识库"，FINAL 仍要求至少一次 SEARCH
        if not time_checked and any(kw in question for kw in TIME_KEYWORDS):
            time_checked = True
            messages.append({"role": "user", "content": f"[当前时间：{_now_str()}]"})

        # 网络结果已就绪但 LLM 可能继续 SEARCH：提示可以直接回答
        if web_used and step > 0:
            messages.append({"role": "user", "content": "你已经通过网络搜索获得了相关信息，请基于这些结果直接输出 FINAL 回答，不要再 SEARCH 了。"})

        try:
            reply = call_llm(messages)
        except requests.exceptions.Timeout:
            return "服务响应超时，请稍后再试。", []
        except requests.exceptions.RequestException as e:
            return f"调用大模型失败：{str(e)[:100]}", []

        # 记录本轮回复
        messages.append({"role": "assistant", "content": reply.strip()})

        # 解析回复中所有工具调用（FINAL / TIME / SEARCH / WEB_SEARCH）
        import re
        tokens = []
        # 用更精确的正则：指令参数取到下一个指令前为止（避免粘连）
        for m in re.finditer(r"(FINAL|TIME|SEARCH|WEB_SEARCH)\s*:?\s*(.*?)(?=\n\s*(?:FINAL|TIME|SEARCH|WEB_SEARCH)\s*:|\Z)", reply, re.DOTALL):
            cmd = m.group(1).strip()
            arg = m.group(2).strip()
            # SEARCH/TIME/WEB_SEARCH 参数只取第一行（后面的换行是说明文字）
            if cmd in ("SEARCH", "TIME", "WEB_SEARCH"):
                arg = arg.split("\n")[0].strip()
            if cmd == "SEARCH":
                # 截断粘连在参数里的下一个指令
                arg = re.split(r"\s*(?:FINAL|TIME|SEARCH|WEB_SEARCH)\s*:", arg)[0].strip()
            tokens.append((cmd, arg))

        if not tokens:
            # 没有任何指令：可能是直接回答，但没检索过知识库就必须先检索
            if searched:
                return reply.strip(), used_sources
            messages.append({"role": "user", "content": "你还没有检索过校园信息库，不能直接回答。请先调用 SEARCH 检索相关课程/信息，再根据检索结果回答。"})
            continue

        # 防编造：同一回复里既有 SEARCH/WEB_SEARCH 又有 FINAL 时，FINAL 是 LLM 编的（还没看真实结果），丢弃
        cmds_in_reply = [t[0] for t in tokens]
        has_search = ("SEARCH" in cmds_in_reply) or ("WEB_SEARCH" in cmds_in_reply) or ("TIME" in cmds_in_reply)
        if "FINAL" in cmds_in_reply and has_search:
            # 只保留非 FINAL 指令，FINAL 丢弃
            tokens = [t for t in tokens if t[0] != "FINAL"]

        # 逐个执行工具调用（同一回复可含多个）
        for cmd, arg in tokens:
            if cmd == "FINAL":
                answer = arg.strip()
                answer = _normalize_source_line(answer)  # 来源标注合并为一行
                answer = _clean_answer(answer)           # 合并正文单换行
                if answer and searched:
                    return answer, used_sources
                if answer and not searched:
                    # 没检索过知识库就 FINAL：提示后继续循环
                    messages.append({"role": "user", "content": "你还没有检索过校园信息库，不能直接回答。请先调用 SEARCH 检索相关课程/信息，再根据检索结果回答。"})
            elif cmd == "TIME":
                tool_used = True
                time_checked = True
                messages.append({"role": "user", "content": f"[{_now_str()}]"})
            elif cmd == "SEARCH":
                searched = True
                result_text = _run_search(arg)
                messages.append({"role": "user", "content": result_text})
            elif cmd == "WEB_SEARCH":
                searched = True
                tool_used = True
                web_used = True
                web_text = web_search(arg)
                messages.append({"role": "user", "content": f"网络搜索结果：\n{web_text}"})

    return "抱歉，检索次数过多仍未找到答案，请换个问法。", used_sources
