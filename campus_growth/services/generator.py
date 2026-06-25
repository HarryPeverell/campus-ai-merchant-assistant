"""校园节点、活动、内容与评论的真实/本地生成。"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

from .ai_request import complete, configured


def _items(value: Any) -> str:
    return "、".join(value) if isinstance(value, list) else str(value or "未设置")


def profile_text(profile: Dict[str, Any]) -> str:
    return "店铺：{store_name}\n主营：{business_type}\n商品/服务：{products}\n价格：{price_range}\n学校：{school_name}\n学生：{students}\n营业：{hours}\n优惠：{offers}\n渠道：{channels}".format(
        **profile, students=_items(profile.get("target_students")), hours=profile.get("business_hours") or "未设置",
        offers=_items(profile.get("discount_options")), channels=_items(profile.get("channels")),
    )


def campus_nodes(weather: Dict[str, Any], calendar: Dict[str, Any], manual_tags: Iterable[str] = ()) -> Tuple[List[str], str]:
    tags: List[str] = list(weather.get("tags", []))
    summary = str(calendar.get("parsed_summary", ""))
    for keyword, tag in (("考试", "考试周"), ("毕业", "毕业季"), ("运动会", "运动会"), ("社团", "社团招新"), ("开学", "开学季"), ("放假", "放假前")):
        if keyword in summary:
            tags.append(tag)
    if date.today().weekday() >= 5:
        tags.append("周末")
    tags.extend(str(x).strip() for x in manual_tags if str(x).strip())
    tags = list(dict.fromkeys(tags))
    if "考试周" in tags:
        time_slot = "12:00-13:30、19:00-22:00"
    elif "雨天" in tags or "雨雪天" in tags:
        time_slot = "11:30-13:30、17:00-20:00"
    elif "周末" in tags:
        time_slot = "14:00-17:00、19:00-21:00"
    else:
        time_slot = "11:30-13:30、16:30-19:00"
    return tags, time_slot


def local_campaign(profile: Dict[str, Any], weather: Dict[str, Any], tags: List[str], time_slot: str,
                   objective: str = "提升到店量", offer: str = "") -> str:
    product = str(profile.get("products", "招牌商品")).split("、")[0].split("，")[0]
    business = str(profile.get("business_type", "店铺"))
    if "考试周" in tags:
        name, scene = "复习续能计划", "图书馆复习、晚自习"
    elif "雨天" in tags or "雨雪天" in tags:
        name, scene = "雨天暖心补给", "避雨、外卖与到店即取"
    elif "高温" in tags:
        name, scene = "清凉补给计划", "午后解暑"
    elif "周末" in tags:
        name, scene = "周末同学搭子套餐", "宿舍、社团聚会"
    else:
        name, scene = "校园今日补给", "上下课与放学时段"
    mechanism = offer or (_items(profile.get("discount_options")) if profile.get("discount_options") else "到店出示校园卡享套餐优惠")
    return """【本地规则生成 · 可直接编辑】
活动名称：{name}
活动目标：{objective}
活动时间：{time_slot}
当前校园节点：{tags}
活动机制：{mechanism}
推荐商品/服务：{product}
适合场景：{scene}
适合渠道：{channels}
风险提示：请以门店实际库存、价格和营业时间为准，优惠不宜超过毛利范围。""".format(
        name=name, objective=objective or "提升到店量", time_slot=time_slot, tags="、".join(tags) or "常规经营", mechanism=mechanism,
        product=product, scene=scene, channels=_items(profile.get("channels")) or "微信群、朋友圈",
    )


def generate_campaign(profile: Dict[str, Any], weather: Dict[str, Any], calendar: Dict[str, Any], tags: List[str],
                      time_slot: str, settings: Dict[str, Any], objective: str = "", offer: str = "") -> Tuple[str, str]:
    fallback = local_campaign(profile, weather, tags, time_slot, objective, offer)
    if not configured(settings):
        return fallback, "本地规则生成（演示）"
    prompt = """你是熟悉校园商圈的小微商家运营顾问。根据资料生成一份可执行的今日促销方案。
【店铺】\n{profile}\n【天气】{weather}\n【校历】{calendar}\n【节点】{tags}\n【推荐时段】{time}\n【活动目标】{objective}\n【优惠偏好】{offer}
输出固定七项：活动名称、活动目标、活动时间、活动机制、推荐商品/服务、适合发布渠道、风险提示。不要编造不存在的商品、校园活动或效果承诺。""".format(
        profile=profile_text(profile), weather=weather, calendar=calendar.get("parsed_summary", "未配置"),
        tags="、".join(tags) or "无", time=time_slot, objective=objective or "提升到店量", offer=offer or "按店铺可接受优惠方式",
    )
    try:
        return complete(settings, prompt, stream=False), "AI 生成"
    except Exception as exc:
        return fallback + "\n\nAI 调用失败，已切换本地规则：{}".format(exc), "本地规则生成（AI 调用失败）"


def local_content(channel: str, campaign: str, profile: Dict[str, Any]) -> str:
    name = next((line.split("：", 1)[1] for line in campaign.splitlines() if line.startswith("活动名称：")), "今日校园活动")
    store = profile.get("store_name", "本店")
    if channel == "微信群":
        return "【{}】{} 今天安排上啦！同学们路过学校附近可来店领取校园福利，数量按门店实际库存为准。想参加直接到店问店员～".format(name, store)
    if channel == "朋友圈":
        return "今天给学校附近的同学准备了「{}」。{} 正在营业，路过、下课或晚自习前都可以来补给一下。活动以门店现场说明为准，欢迎来问～".format(name, store)
    if channel == "小红书":
        return "标题备选：\n1. 学校附近这家店的今日补给\n2. 下课路过可以试试的校园福利\n3. 复习/下课党的小确幸\n\n正文：\n{} 今天做了「{}」，适合下课、复习或和同学一起路过时顺手带一份。活动规则已写在店内，按实际库存供应，不夸张但很实在。\n\n标签：#校园生活 #学校周边 #学生党 #今日福利 #本地探店".format(store, name)
    if channel == "抖音":
        return "15-30 秒脚本\n镜头 1（3 秒）：学校周边/门店招牌，字幕：下课路过的补给站。\n镜头 2（8 秒）：展示制作或服务过程，口播：今天有「{}」。\n镜头 3（8 秒）：展示活动信息，口播：具体规则以门店现场为准。\n镜头 4（4 秒）：店门口与行动引导，字幕：路过来问问。".format(name)
    if channel == "海报":
        return "海报标题：{}\n副标题：学校周边同学专属补给\n活动信息：{}\n行动引导：到店咨询店员，按现场规则参与。\n提示：活动时间、价格与库存以门店实际为准。".format(name, store)
    return "{}\n{}".format(name, campaign)


def generate_content(channel: str, campaign: str, profile: Dict[str, Any], settings: Dict[str, Any]) -> Tuple[str, str]:
    fallback = local_content(channel, campaign, profile)
    if not configured(settings):
        return fallback, "本地规则生成（演示）"
    requirements = {"微信群": "50-100 字，短促直接，有行动引导", "朋友圈": "100-150 字，自然有生活感", "小红书": "3 个标题、150-300 字正文和 5-8 个标签", "抖音": "15-30 秒分镜、画面和口播", "海报": "标题、副标题、活动规则、行动引导，短句化"}
    prompt = """根据活动方案和店铺信息生成 {channel} 内容。{requirement}。
不得虚假夸张、不得承诺效果、不得编造商品或学校活动；规则与价格以门店实际为准。
【店铺】{profile}\n【活动】{campaign}""".format(channel=channel, requirement=requirements[channel], profile=profile_text(profile), campaign=campaign)
    try:
        return complete(settings, prompt, stream=bool(settings.get("stream", False))), "AI 生成"
    except Exception as exc:
        return fallback + "\n\nAI 调用失败，已切换本地规则：{}".format(exc), "本地规则生成（AI 调用失败）"


def generate_reply(comment: str, comment_type: str, tone: str, profile: Dict[str, Any], settings: Dict[str, Any]) -> Tuple[str, str]:
    if comment_type == "差评":
        fallback = "非常抱歉给你带来不好的体验，我们已经记录你反馈的问题并会认真改进。方便的话请私信我们订单/到店时间，我们会尽快核实并处理。"
    elif comment_type == "好评":
        fallback = "谢谢你的喜欢和支持！很开心能为你服务，欢迎下次路过再来～"
    elif comment_type == "催单":
        fallback = "抱歉让你久等了，我们正在尽快处理，辛苦稍等一下；如有需要可私信我们核对订单。"
    else:
        fallback = "你好，{} 位于{}，营业时间为{}。具体价格和活动规则以门店现场为准，欢迎私信或到店咨询。".format(profile.get("store_name", "本店"), profile.get("address") or "学校附近", profile.get("business_hours") or "请联系店员确认")
    if not configured(settings):
        return fallback, "本地规则生成（演示）"
    prompt = """为商家生成一条公开回复。评论类型：{kind}；语气：{tone}。
店铺资料：{profile}\n用户评论：{comment}
差评必须先致歉，再表达改进/处理，并引导私聊；不要攻击用户、推卸责任或承诺无法保证的结果。""".format(kind=comment_type, tone=tone, profile=profile_text(profile), comment=comment)
    try:
        return complete(settings, prompt, stream=bool(settings.get("stream", False))), "AI 生成"
    except Exception as exc:
        return fallback + "\n\nAI 调用失败，已切换本地规则：{}".format(exc), "本地规则生成（AI 调用失败）"
