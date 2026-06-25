"""校历的本地和 AI 分析。"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def _lines_with(text: str, keywords: Tuple[str, ...]) -> List[str]:
    return [line.strip() for line in text.splitlines() if any(word in line for word in keywords)][:8]


def _date_mentions(text: str, keywords: Tuple[str, ...]) -> List[str]:
    pattern = re.compile(r"(?:20\d{2}[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?|\d{1,2}月\d{1,2}日)")
    results: List[str] = []
    for line in _lines_with(text, keywords):
        results.extend(pattern.findall(line) or [line[:80]])
    return list(dict.fromkeys(results))[:6]


def analyze_local(raw_content: str, school_name: str) -> Dict[str, Any]:
    text = raw_content.replace("\x00", "").strip()[:60_000]
    exam_lines = _lines_with(text, ("考试周", "期末考试", "期中考试", "考试安排"))
    holiday_lines = _lines_with(text, ("放假", "寒假", "暑假", "假期"))
    start_dates = _date_mentions(text, ("开学", "报到", "注册"))
    end_dates = _date_mentions(text, ("放假", "学期结束", "结课"))
    week_matches = re.findall(r"第\s*(\d{1,2})\s*(?:[-至到]\s*(\d{1,2}))?\s*周", "\n".join(exam_lines))
    exam_weeks = ["第{}{}周".format(first, "-" + last if last else "") for first, last in week_matches]
    times = re.findall(r"(?:[01]?\d|2[0-3])[:：][0-5]\d", text)
    tags: List[str] = []
    for word, tag in (("考试", "考试周"), ("毕业", "毕业季"), ("运动会", "运动会"), ("社团", "社团招新"), ("开学", "开学季"), ("放假", "放假前")):
        if word in text:
            tags.append(tag)
    tags = list(dict.fromkeys(tags))
    summary = ["学校：{}".format(school_name)]
    if exam_lines:
        summary.append("考试信息：" + "；".join(exam_lines[:3]))
    if holiday_lines:
        summary.append("假期信息：" + "；".join(holiday_lines[:3]))
    if times:
        summary.append("识别到时间：" + "、".join(list(dict.fromkeys(times))[:12]))
    if tags:
        summary.append("校园标签：" + "、".join(tags))
    return {
        "school_name": school_name, "parsed_summary": "\n".join(summary),
        "term_start": "、".join(start_dates), "term_end": "、".join(end_dates),
        "exam_weeks": "、".join(exam_weeks or exam_lines[:3]),
        "holidays": "、".join(holiday_lines[:3]),
        "class_time_slots": "、".join(list(dict.fromkeys(times))[:12]),
        "tags": tags, "source": "本地规则分析（演示）",
    }


def _parse_ai_json(answer: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", answer)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    required = {"parsed_summary", "term_start", "term_end", "exam_weeks", "holidays", "class_time_slots", "tags"}
    if not required.issubset(data):
        return None
    data["tags"] = data["tags"] if isinstance(data["tags"], list) else []
    data["source"] = "AI 校历分析"
    return data


def analyze_calendar(raw_content: str, school_name: str, ai_client: Optional[Any] = None) -> Dict[str, Any]:
    fallback = analyze_local(raw_content, school_name)
    if not ai_client or not ai_client.is_configured:
        return fallback
    prompt = """请分析以下学校校历，只提取明确出现的信息，不要猜测。输出 JSON：
{"parsed_summary":"", "term_start":"", "term_end":"", "exam_weeks":"", "holidays":"", "class_time_slots":"", "tags":["考试周"]}
可用 tags 仅限：开学季、考试周、毕业季、运动会、社团招新、放假前。
学校：{school}\n校历内容：\n{content}""".format(school=school_name, content=raw_content[:20_000])
    try:
        parsed = _parse_ai_json(ai_client.complete(prompt, stream=False))
        if parsed:
            parsed["school_name"] = school_name
            return parsed
    except Exception:
        pass
    return fallback
