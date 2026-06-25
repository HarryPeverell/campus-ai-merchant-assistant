from campus_growth.services.generator import campus_nodes, generate_campaign, generate_content, generate_reply


PROFILE = {
    "store_name": "东门柠檬茶", "business_type": "奶茶", "products": "热柠檬茶、芋泥奶茶",
    "price_range": "12-25 元", "school_name": "示例大学", "target_students": ["本科生"],
    "discount_options": ["第二杯半价"], "business_hours": "10:00-22:00", "channels": ["微信群", "朋友圈"],
}


def test_exam_rain_campaign_uses_local_fallback():
    weather = {"weather": "小雨", "tags": ["雨天"]}
    calendar = {"parsed_summary": "考试信息：第 16 周期末考试"}
    tags, slot = campus_nodes(weather, calendar, ["运动会"])
    assert {"雨天", "考试周", "运动会"}.issubset(tags)
    text, source = generate_campaign(PROFILE, weather, calendar, tags, slot, {}, "提升晚间到店量")
    assert "活动名称" in text and "考试" in text
    assert "本地规则" in source


def test_channels_and_bad_review_are_safe_without_ai():
    campaign = "活动名称：图书馆续能计划\n活动机制：第二杯半价"
    content, source = generate_content("小红书", campaign, PROFILE, {})
    assert "标题备选" in content and "本地规则" in source
    reply, source = generate_reply("太慢了", "差评", "诚恳", PROFILE, {})
    assert "抱歉" in reply and "私信" in reply and "本地规则" in source
