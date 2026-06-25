"""集中维护 V2 的 AI Prompt 模板。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def context_text(context: Dict[str, Any]) -> str:
    profile = context.get("profile", {})
    menu = "、".join("{} {}元".format(x.get("name"), x.get("price")) for x in context.get("menu", [])) or "未配置"
    packages = "、".join("{} {}元".format(x.get("name"), x.get("price")) for x in context.get("packages", [])) or "未配置"
    schools = "；".join("{}：{}，上下课 {}，午间高峰 {}，晚间高峰 {}".format(x.get("name"), x.get("current_node", x.get("node", "正常上课周")), x.get("class_time_slots", "未配置"), x.get("lunch_peak_slots", "未配置"), x.get("evening_peak_slots", "未配置")) for x in context.get("schools", [])) or "未配置"
    events = "；".join("{}（{}，{}至{}）".format(x.get("title"), x.get("school_name", "全店"), x.get("start_date", ""), x.get("end_date", "")) for x in context.get("events", []) if x.get("title")) or "无额外手动事件"
    campaigns_text = "；".join("{}（规则：{}，优惠券核销 {}，到店 {} 人，销售额 ¥{}）".format(x.get("campaign_name"), x.get("discount_rule", {}).get("description", x.get("campaign_plan", "")[:40]), x.get("coupon_used", 0), x.get("visitor_count", 0), x.get("sales_amount", 0)) for x in context.get("campaigns", [])[:5]) or "暂无活动记录"
    date_range_text = context.get("parameters", {}).get("date_range", "近 7 日")
    weather = context.get("weather", {})
    finance = context.get("finance", {})
    package_metrics = "；".join("{}：{} 单，收入 {} 元，优惠成本 {} 元".format(x.get("package_name"), x.get("order_count"), x.get("revenue"), x.get("discount_cost")) for x in context.get("package_metrics", [])) or "暂无套餐表现数据"
    return """店铺信息：{store}；主营：{business}；地址：{address}；营业时间：{hours}
菜单：{menu}
套餐：{packages}
当前时间：{now}
分析范围：{date_range}
天气：{weather}，{temp}℃，标签：{tags}
附近学校与节点：{schools}
手动校园事件：{events}
近七日营收：{revenue} 元，毛利率：{margin}%
当前套餐表现：{package_metrics}
近期活动记录：{campaigns_text}
""".format(
        store=profile.get("store_name", "东门小吃铺"), business=profile.get("business_type", "校园小吃"),
        address=profile.get("address", "大学城附近"), hours=profile.get("business_hours", "10:00-23:00"),
        menu=menu, packages=packages, now=datetime.now().strftime("%Y-%m-%d %H:%M"), date_range=date_range_text,
        weather=weather.get("weather", "小雨"), temp=weather.get("temperature", 18), tags="、".join(weather.get("tags", [])) or "雨天",
        schools=schools, events=events, revenue=finance.get("revenue", 0), margin=finance.get("gross_margin", 0), package_metrics=package_metrics, campaigns_text=campaigns_text,
    )


def build_prompt(kind: str, context: Dict[str, Any]) -> str:
    common = """你是熟悉校园商圈的小微餐饮运营顾问。面向大学生，语言自然、可直接执行；不夸大效果、不编造商品或学校活动，优惠要考虑成本和毛利。
所有输出必须是普通中文纯文本。严禁输出 Markdown 或 LaTeX 格式，严禁使用星号、井号、反引号、美元符号、下划线强调、表格、分隔线、代码块、数学公式、\\( \\)、\\[ \\]、项目符号或编号列表。不要解释你如何生成，也不要出现 AI 自述。
{context}
""".format(context=context_text(context))
    requirements = {
        "今日经营建议": "输出：今日主推单品、推荐套餐、优惠方式、发布时间、发布渠道、适合人群、推荐理由、执行风险。",
        "今日促销方案": "输出：活动名称、活动目标、主推单品/套餐、活动规则、优惠机制、发布时间、发布渠道、风险提醒。",
        "微信群文案": "生成 80 字以内微信群通知，有清晰活动、时间与行动引导。",
        "朋友圈文案": "生成 120 字以内朋友圈文案，有生活感，不要堆砌 emoji。",
        "小红书标题与正文": "第一行只给一个标题，空一行后给正文，再空一行给纯文字标签词；不写标题说明。",
        "抖音短视频脚本": "生成 20 秒脚本，按自然换行给出镜头、画面、口播和收尾行动引导。",
        "海报文案": "按自然换行给出海报标题、卖点、活动规则和行动引导，不写字段名称。",
        "评论回复话术": "根据提供的顾客评论生成 1 条可公开发布的回复；差评先致歉、再改进、最后引导私聊。",
        "私域复购话术": "生成一条不打扰、带关怀的老客复购提醒。",
        "会员召回话术": "生成一条面向 7 天未消费会员的召回话术，避免过度营销。",
        "AI 数据复盘": "分析指定范围内的收入、成本、利润、到店和核销。对比各套餐表现（收入、毛利贡献、优惠成本占比），评估活动对营收的具体影响。输出：表现最好日期、有效活动分析、套餐毛利贡献排名、成本异常提醒、优惠成本评估、明日具体执行建议和优惠调整建议。",
    }
    extra = requirements.get(kind, "生成清晰、可复制的校园商家运营内容。")
    parameters = context.get("parameters", {})
    direct_kinds = {"微信群文案", "朋友圈文案", "小红书标题与正文", "抖音短视频脚本", "海报文案", "评论回复话术", "私域复购话术", "会员召回话术"}
    direct_rule = "\n只输出最终可直接复制发送的正文。不要写字段标题、标题说明、免责声明或引号；不要使用 Markdown、LaTeX、星号、井号、项目符号、编号列表、分隔线、代码块或 AI 自述。" if kind in direct_kinds else "\n按自然换行输出纯文本，不要使用 Markdown、LaTeX、项目符号、编号列表或表格。"
    return common + "任务：{}\n参数：{}\n{}{}".format(kind, parameters, extra, direct_rule)
