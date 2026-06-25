"""统一 AI 调用与完全可运行的 Mock 回退。"""
from __future__ import annotations

import re
from typing import Any, Dict

from campus_growth.prompt_templates import build_prompt
from campus_growth.services.ai_request import complete, configured


DIRECT_KINDS = {"微信群文案", "朋友圈文案", "小红书标题与正文", "抖音短视频脚本", "海报文案", "评论回复话术", "私域复购话术", "会员召回话术"}


def clean_direct_content(content: str) -> str:
    """去除模型常见的 Markdown/解释包装，复制区只保留可发布正文。"""
    content = content.replace("**", "").replace("__", "").replace("~~", "").replace("*", "").replace("#", "").replace("`", "").replace("$", "")
    content = re.sub(r"\\\(|\\\)|\\\[|\\\]|\\begin\{[^}]+\}|\\end\{[^}]+\}", "", content)
    content = re.sub(r"^\s*>\s*", "", content, flags=re.MULTILINE)
    lines = []
    for line in content.splitlines():
        value = re.sub(r"^\s*(?:[-•●]|\d+[.、])\s*", "", line).strip()
        if re.match(r"^(以下是|这是|文案如下|生成结果|说明[：:]|提示[：:])", value):
            continue
        lines.append(value)
    return "\n".join(lines).strip()


def _choice(context: Dict[str, Any], name: str, fallback: str) -> str:
    for item in context.get(name, []):
        if item.get("is_active", 1):
            return item.get("name", fallback)
    return fallback


def mock_content(kind: str, context: Dict[str, Any]) -> str:
    profile = context.get("profile", {}); store = profile.get("store_name", "东门小吃铺")
    package = _choice(context, "packages", "关东煮豆浆套餐")
    weather = context.get("weather", {}).get("weather", "小雨")
    if kind == "今日经营建议":
        return """今日主推单品：关东煮三件套、热豆浆
今日推荐套餐：{package}
推荐优惠：学生凭校园卡立减 2 元，不与其他优惠叠加
推荐发布时间：17:30、20:30
推荐渠道：微信群、朋友圈、小红书
适合人群：晚自习学生、考试周复习学生
推荐理由：今天 {weather}，且北京科技大学处于考试周，热食和快速外带能覆盖晚饭与晚自习后高峰。
执行风险：套餐价格不低于 13 元；高峰前备好关东煮与热豆浆，避免等待过长。""".format(package=package, weather=weather)
    if kind == "今日促销方案":
        return """活动名称：雨天复习暖胃计划
活动目标：提升晚间客流与考试周转化
主推套餐：{package}
活动规则：17:30-22:00 到店出示校园卡立减 2 元；数量按现场备货为准。
推荐发布时间：17:30、20:30
推荐渠道：微信群、朋友圈
风险提醒：优惠不叠加，关注热豆浆和关东煮库存。""".format(package=package)
    if kind == "微信群文案":
        return "{store} 今天雨天又赶上考试周，晚自习前来一份 {package} 暖暖胃。17:30 到 22:00 出示校园卡立减 2 元，数量按现场备货，路过直接来拿。".format(store=store, package=package)
    if kind == "朋友圈文案":
        return "北京这场雨有点凉，晚自习前给同学们备了 {package}。{store} 17:30 后出示校园卡立减 2 元，关东煮和热豆浆都在热着，路过就来补给一下。".format(store=store, package=package)
    if kind == "小红书标题与正文":
        return """学院路雨天晚自习的暖胃小吃

今天学院路下雨，晚自习前最想来点热乎的。{store} 的 {package} 把饭团、关东煮和热豆浆都配好了，适合赶时间的复习党。路过可以直接到店问店员，热乎乎拿了就走。

北京校园生活 学院路美食 考试周 晚自习 学生党""".format(store=store, package=package)
    if kind == "抖音短视频脚本":
        return """镜头一  雨天学院路门头，字幕 晚自习前吃点热的
镜头二  关东煮冒热气，倒入热豆浆，口播 考试周的暖胃组合来了
镜头三  展示 {package}，口播 校园卡到店立减 2 元
镜头四  学生外带离店，字幕 17:30 到 22:00 路过就来""".format(package=package)
    if kind == "海报文案":
        return """雨天复习暖胃计划
晚自习前 来一份热乎乎的能量
{package}
17:30 到 22:00 校园卡立减 2 元
学院路东门小吃铺 到店即取""".format(package=package)
    if kind == "评论回复话术":
        return "很抱歉让你久等了，我们已记录出餐速度的问题，会在晚高峰提前备餐。方便的话请私信到店时间或订单信息，我们会尽快核实处理。"
    if kind == "私域复购话术":
        return "这两天降温，给老同学留了一份热乎的 {package}。路过学院路可以来店问问，不着急，想吃的时候再来就好～".format(package=package)
    if kind == "会员召回话术":
        return "好久没见啦～这周考试周，东门小吃铺准备了关东煮豆浆套餐。到店报会员就能领校园卡立减，愿你复习顺利、吃得热乎。"
    if kind == "AI 数据复盘":
        return """表现最好：最近一天收入 920 元，到店 74 人，关东煮豆浆套餐带动了晚间高峰。
有效活动：饭团关东煮豆浆套餐核销表现更好，说明复习场景与热食组合匹配。
成本观察：优惠成本占收入比例可控，推广投入建议集中在 17:30 前。
明日建议：继续主推关东煮三件套 + 热豆浆；若天气转晴，可增加柠檬茶曝光。
优惠建议：保持校园卡立减 2 元，不建议叠加第二件半价。"""
    return "{} 已生成一份可编辑的校园商家运营内容。".format(kind)


class AIService:
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

    @property
    def is_mock_mode(self) -> bool:
        return not configured(self.settings)

    def generate(self, kind: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.is_mock_mode:
            content = mock_content(kind, context)
            return {"content": clean_direct_content(content), "source": "演示模式 · Mock AI", "is_mock": True}
        try:
            answer = complete(self.settings, build_prompt(kind, context), stream=bool(self.settings.get("stream", False)))
            return {"content": clean_direct_content(answer), "source": "AI 生成", "is_mock": False}
        except Exception as exc:
            content = mock_content(kind, context)
            return {"content": clean_direct_content(content), "source": "演示模式 · AI 调用失败", "is_mock": True}

    def today_advice(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.generate("今日经营建议", context)

    def review_finance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.generate("AI 数据复盘", context)
