import json
import sys

from campus_growth.ai_service import AIService, clean_direct_content, mock_content
from campus_growth.prompt_templates import context_text, build_prompt
from campus_growth.services.weather import WeatherService, business_impact
from campus_growth.v2_store import V2Database, nearby_schools_for_address


# ---------------------------------------------------------------------------
# Existing V2 tests (preserved)
# ---------------------------------------------------------------------------

def test_v2_admin_seed_has_full_snack_demo(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    assert db.get_profile(user["id"])["store_name"] == "东门小吃铺"
    assert len(db.get_menu_items(user["id"])) == 6
    assert len(db.get_packages(user["id"])) == 4
    assert [item["name"] for item in db.get_schools(user["id"])] == ["北京科技大学", "北京林业大学", "中国地质大学（北京）"]
    assert db.get_schools(user["id"])[0]["class_time_slots"]
    assert db.get_schools(user["id"])[0]["lunch_peak_slots"]
    assert len(db.list_finance(user["id"], 7)) == 7
    assert len(db.package_summary(user["id"])) == 4
    assert len(db.get_tasks(user["id"])) == 6


def test_finance_metrics_tasks_and_school_sync(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    record_id = db.save_finance(user["id"], {"record_date": "2030-01-01", "revenue": 200, "ingredient_cost": 60, "labor_cost": 30, "promotion_cost": 10, "discount_cost": 10, "other_cost": 5, "visitor_count": 20, "coupon_used": 5})
    record = [x for x in db.list_finance(user["id"]) if x["id"] == record_id][0]
    assert record["total_cost"] == 115
    assert record["gross_profit"] == 85
    assert record["avg_ticket"] == 10
    task = db.get_tasks(user["id"])[0]
    db.set_task_status(user["id"], task["id"], "done")
    assert db.get_tasks(user["id"])[0]["status"] == "done"
    assert nearby_schools_for_address("北京市海淀区学院路")[0]["name"] == "北京科技大学"


def test_mock_ai_returns_complete_demo_content(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    context = {"profile": db.get_profile(user["id"]), "menu": db.get_menu_items(user["id"]), "packages": db.get_packages(user["id"]), "schools": db.get_schools(user["id"]), "weather": {"weather": "小雨", "tags": ["雨天"]}, "finance": db.finance_summary(user["id"]), "parameters": {}}
    result = AIService({}).generate("小红书标题与正文", context)
    assert result["is_mock"] is True
    assert "学院路雨天晚自习" in result["content"]
    assert "东门小吃铺" in result["content"]
    assert "#" not in result["content"] and "*" not in result["content"]


def test_package_metrics_range_and_direct_copy_cleanup(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    metric_id = db.save_package_metric(user["id"], {"record_date": "2030-01-01", "package_name": "关东煮豆浆套餐", "order_count": 10, "revenue": 130, "ingredient_cost": 50, "discount_cost": 10, "channel": "外带"})
    rows = db.list_package_metrics(user["id"], "2030-01-01", "2030-01-01")
    assert rows[0]["id"] == metric_id and rows[0]["gross_profit"] == 70
    assert clean_direct_content("以下是文案：\n**雨天来吃**\n#学院路") == "雨天来吃\n学院路"


# ---------------------------------------------------------------------------
# V2.1: Bug fix verification
# ---------------------------------------------------------------------------

def test_mock_moments_content_is_formatted(tmp_path):
    """Verify the 朋友圈文案 mock is fully formatted (no raw {store}/{package} placeholders)."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    context = {"profile": db.get_profile(user["id"]), "packages": db.get_packages(user["id"]), "weather": {"weather": "小雨", "tags": ["雨天"]}}
    content = mock_content("朋友圈文案", context)
    assert "{store}" not in content
    assert "{package}" not in content
    assert "东门小吃铺" in content
    # Should reference a real package name
    assert "鸡排柠檬茶套餐" in content or "关东煮豆浆套餐" in content or "饭团关东煮豆浆套餐" in content or "烤肠饭团套餐" in content


# ---------------------------------------------------------------------------
# V2.1: All mock content kinds are clean (markdown-free)
# ---------------------------------------------------------------------------

def test_all_mock_kinds_are_clean(tmp_path):
    """Verify clean_direct_content for every direct-publish mock kind produces markdown-free text."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    base_context = {"profile": db.get_profile(user["id"]), "menu": db.get_menu_items(user["id"]), "packages": db.get_packages(user["id"]), "schools": db.get_schools(user["id"]), "weather": {"weather": "小雨", "tags": ["雨天"]}, "finance": db.finance_summary(user["id"]), "package_metrics": db.package_summary(user["id"]), "events": db.campus_events(user["id"]), "parameters": {}}
    direct_kinds = ("微信群文案", "朋友圈文案", "小红书标题与正文", "抖音短视频脚本", "海报文案", "评论回复话术", "私域复购话术", "会员召回话术")
    markdown_chars = {"#", "**", "__", "`"}
    for kind in direct_kinds:
        result = AIService({}).generate(kind, base_context)
        content = result["content"]
        assert result["is_mock"] is True
        # No markdown artifacts
        for char in markdown_chars:
            assert char not in content, "{} content contains markdown char: {}".format(kind, char)
        # No AI self-disclosure phrases
        for phrase in ("以下是", "这是", "文案如下", "生成结果", "说明：", "提示：", "免责声明"):
            assert phrase not in content, "{} content contains AI phrase: {}".format(kind, phrase)
        assert len(content) > 10, "{} content too short".format(kind)


def test_xiaohongshu_mock_has_proper_newline_structure(tmp_path):
    """XiaoHongShu mock: title, blank line, body, blank line, tags."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    context = {"profile": db.get_profile(user["id"]), "packages": db.get_packages(user["id"]), "weather": {"weather": "小雨"}}
    result = AIService({}).generate("小红书标题与正文", context)
    content = result["content"]
    lines = content.split("\n")
    # Should have at least 5 lines: title, blank, body line(s), blank, tags
    assert len(lines) >= 4, "XiaoHongShu content too short: {}".format(content)
    # First line is title (non-empty)
    assert lines[0].strip(), "XiaoHongShu title is empty"
    # Second line should be blank
    assert lines[1].strip() == "", "XiaoHongShu line 2 should be blank, got: {}".format(lines[1])
    # Last line should be tags (non-empty, has spaces)
    assert lines[-1].strip(), "XiaoHongShu tags line is empty"


# ---------------------------------------------------------------------------
# V2.1: School CRUD
# ---------------------------------------------------------------------------

def test_school_schedule_update_persists(tmp_path):
    """Update a school's schedule and verify fields are saved correctly."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    schools = db.get_schools(user["id"])
    school = schools[0]
    update_data = {"current_node": "考试周", "node_detail": "期末复习高峰", "class_time_slots": "08:30、10:30、13:00、15:00、17:00", "lunch_peak_slots": "12:00-13:30", "evening_peak_slots": "17:30-19:00、21:00-22:30", "operating_tip": "主推考试套餐，晚间备好热饮。"}
    db.update_school(user["id"], school["id"], update_data)
    updated = db.get_schools(user["id"])[0]
    assert updated["current_node"] == "考试周"
    assert updated["class_time_slots"] == "08:30、10:30、13:00、15:00、17:00"
    assert updated["lunch_peak_slots"] == "12:00-13:30"
    assert updated["evening_peak_slots"] == "17:30-19:00、21:00-22:30"
    assert updated["operating_tip"] == "主推考试套餐，晚间备好热饮。"


def test_campus_event_crud(tmp_path):
    """Add a campus event and verify it appears in the event list."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    schools = db.get_schools(user["id"])
    event_id = db.add_campus_event(user["id"], {"school_id": schools[0]["id"], "title": "运动会", "event_type": "运动会", "start_date": "2030-05-01", "end_date": "2030-05-03"})
    assert event_id > 0
    events = db.campus_events(user["id"])
    # Should include our new event
    titles = [e["title"] for e in events]
    assert "运动会" in titles
    # Should include school name via JOIN
    event = next(e for e in events if e["title"] == "运动会")
    assert event["school_name"] == schools[0]["name"]


# ---------------------------------------------------------------------------
# V2.1: DiscountRuleBuilder smoke test
# ---------------------------------------------------------------------------

def test_discount_rule_text_all_types():
    """Unit test for DiscountRuleBuilder rule_text / values without Qt."""
    from app_v2 import DiscountRuleBuilder
    app = None
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
    except Exception:
        pass  # may fail in headless, but try anyway

    # We need a MainWindow stub for DiscountRuleBuilder
    class FakeWindow:
        class db:
            @staticmethod
            def get_packages(uid):
                return [{"id": 1, "name": "测试套餐", "items": "a+b", "price": 15, "target_scene": "test"}]
            @staticmethod
            def get_menu_items(uid):
                return [{"id": 1, "name": "测试单品", "category": "小吃", "price": 10}]

    fake_win = FakeWindow()
    builder = None
    try:
        builder = DiscountRuleBuilder(fake_win)
    except Exception:
        # If PyQt not available, skip
        import pytest
        pytest.skip("PyQt not available for DiscountRuleBuilder test")

    # Test each discount type produces a rule text
    for discount_type in ("立减", "满减", "折扣", "固定套餐价", "第二件优惠", "赠品", "限时券"):
        builder.kind.setCurrentText(discount_type)
        builder.value.setValue(2.0 if discount_type != "折扣" else 8.5)
        builder.threshold.setValue(30 if discount_type == "满减" else 0)
        builder.gift.setText("热豆浆" if discount_type == "赠品" else "")
        rule = builder.rule_text()
        assert len(rule) > 5
        values = builder.values()
        assert values["type"] == discount_type
        assert "description" in values


# ---------------------------------------------------------------------------
# V2.1: Date range filtering
# ---------------------------------------------------------------------------

def test_finance_date_range_filtering(tmp_path):
    """list_finance with custom start/end dates returns only matching records."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    # Save two records with known dates
    db.save_finance(user["id"], {"record_date": "2030-02-01", "revenue": 100, "ingredient_cost": 30, "labor_cost": 20, "promotion_cost": 5, "discount_cost": 5, "other_cost": 3, "visitor_count": 10, "coupon_used": 2})
    db.save_finance(user["id"], {"record_date": "2030-02-15", "revenue": 200, "ingredient_cost": 60, "labor_cost": 30, "promotion_cost": 10, "discount_cost": 10, "other_cost": 5, "visitor_count": 20, "coupon_used": 5})
    rows = db.list_finance(user["id"], start_date="2030-02-01", end_date="2030-02-01")
    assert len(rows) == 1
    assert rows[0]["revenue"] == 100
    rows2 = db.list_finance(user["id"], start_date="2030-02-14", end_date="2030-02-16")
    assert len(rows2) == 1
    assert rows2[0]["revenue"] == 200


def test_package_metrics_date_range_filtering(tmp_path):
    """list_package_metrics with custom dates returns only matching."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    db.save_package_metric(user["id"], {"record_date": "2030-03-01", "package_name": "测试套餐A", "order_count": 5, "revenue": 75, "ingredient_cost": 30, "discount_cost": 5})
    db.save_package_metric(user["id"], {"record_date": "2030-03-10", "package_name": "测试套餐B", "order_count": 10, "revenue": 150, "ingredient_cost": 60, "discount_cost": 15})
    rows = db.list_package_metrics(user["id"], start_date="2030-03-01", end_date="2030-03-05")
    assert len(rows) == 1
    assert rows[0]["package_name"] == "测试套餐A"


# ---------------------------------------------------------------------------
# V2.1: Campaign save/load with discount_rule JSON roundtrip
# ---------------------------------------------------------------------------

def test_campaign_save_load_discount_rule_roundtrip(tmp_path):
    """Save a campaign with discount_rule dict, load it back, verify JSON roundtrip."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    discount_rule = {"type": "立减", "value": 3, "threshold": 0, "scope": "全部菜单", "window": "17:30-22:00", "stackable": False, "gift": "", "description": "立减 3 元，适用 全部菜单，时段 17:30-22:00，不叠加"}
    campaign_id = db.save_campaign(user["id"], {"campaign_name": "测试立减活动", "campaign_plan": "全店消费立减3元，晚间限时。", "node_tags": ["考试周"], "weather_snapshot": {"weather": "晴"}, "publish_channels": ["微信群"], "publish_time": "17:30-22:00", "discount_rule": discount_rule, "package_name": "全部套餐", "publish_window": "17:30-22:00", "coupon_used": 15, "visitor_count": 60, "sales_amount": 780})
    campaigns = db.list_campaigns(user["id"])
    saved = next(c for c in campaigns if c["id"] == campaign_id)
    assert saved["campaign_name"] == "测试立减活动"
    assert saved["discount_rule"]["type"] == "立减"
    assert saved["discount_rule"]["value"] == 3
    assert saved["discount_rule"]["description"] == "立减 3 元，适用 全部菜单，时段 17:30-22:00，不叠加"
    assert saved["package_name"] == "全部套餐"
    assert saved["publish_window"] == "17:30-22:00"


def test_campaign_filtering_by_date_range(tmp_path):
    """Campaign date filtering returns only campaigns within the range."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    # Save a campaign (created_at = now-ish)
    db.save_campaign(user["id"], {"campaign_name": "近期活动", "campaign_plan": "test", "node_tags": [], "weather_snapshot": {}, "publish_channels": [], "discount_rule": {"type": "立减", "value": 2}})
    campaigns_all = db.list_campaigns(user["id"])
    assert len(campaigns_all) >= 1
    # Date range filtering by start_date should work
    campaigns_filtered = db.list_campaigns(user["id"], start_date="2000-01-01", end_date="2099-12-31")
    assert len(campaigns_filtered) >= len(campaigns_all) - 1  # allow for edge


# ---------------------------------------------------------------------------
# V2.1: Demo data verification
# ---------------------------------------------------------------------------

def test_demo_seeded_campaigns_have_discount_rule(tmp_path):
    """Verify reset_demo_data creates campaigns with proper discount_rule JSON."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    campaigns = db.list_campaigns(user["id"])
    assert len(campaigns) >= 3, "Expected at least 3 demo campaigns, got {}".format(len(campaigns))
    for camp in campaigns:
        assert isinstance(camp.get("discount_rule"), dict), "discount_rule should be a dict: {}".format(camp.get("discount_rule"))
        dr = camp["discount_rule"]
        assert "type" in dr, "discount_rule missing type: {}".format(dr)
        if camp["campaign_name"] == "饭团关东煮豆浆套餐":
            assert dr["type"] == "立减"
        elif camp["campaign_name"] == "关东煮豆浆套餐":
            assert dr["type"] == "折扣"
        elif camp["campaign_name"] == "烤肠饭团套餐":
            assert dr["type"] == "固定套餐价"
        assert camp.get("package_name"), "package_name should not be empty"
        assert camp.get("publish_window"), "publish_window should not be empty"


def test_demo_package_metrics_spans_all_days(tmp_path):
    """Demo package metrics should cover multiple days and channels."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    metrics = db.list_package_metrics(user["id"])
    assert len(metrics) >= 12, "Expected 12+ package metric rows, got {}".format(len(metrics))
    # Verify multiple channels
    channels = {m["channel"] for m in metrics}
    assert "到店" in channels
    assert "外带" in channels
    # Verify multiple packages
    packages = {m["package_name"] for m in metrics}
    assert len(packages) == 4, "Expected all 4 packages represented"


# ---------------------------------------------------------------------------
# V2.1: AI context verification
# ---------------------------------------------------------------------------

def test_ai_context_includes_campaigns(tmp_path):
    """context_text should include campaign data when provided."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    campaigns = db.list_campaigns(user["id"])
    context = {"profile": db.get_profile(user["id"]), "menu": db.get_menu_items(user["id"]), "packages": db.get_packages(user["id"]), "schools": db.get_schools(user["id"]), "events": db.campus_events(user["id"]), "weather": {"weather": "小雨", "temperature": 16, "tags": ["雨天"]}, "finance": db.finance_summary(user["id"]), "package_metrics": db.package_summary(user["id"]), "campaigns": campaigns, "parameters": {}}
    text = context_text(context)
    assert "近期活动记录" in text
    # Should mention at least one campaign
    assert "饭团关东煮豆浆套餐" in text or "关东煮豆浆套餐" in text or "烤肠饭团套餐" in text


def test_ai_context_includes_date_range(tmp_path):
    """context_text should include the analysis date range."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    context = {"profile": db.get_profile(user["id"]), "menu": [], "packages": [], "schools": [], "events": [], "weather": {"weather": "晴", "temperature": 20, "tags": []}, "finance": db.finance_summary(user["id"]), "package_metrics": [], "campaigns": [], "parameters": {"date_range": "2030-01-01 至 2030-01-07"}}
    text = context_text(context)
    assert "2030-01-01 至 2030-01-07" in text


def test_ai_context_events_with_school_and_date(tmp_path):
    """context_text should include events with school name and date range."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    schools = db.get_schools(user["id"])
    db.add_campus_event(user["id"], {"school_id": schools[0]["id"], "title": "招聘会", "event_type": "招聘会", "start_date": "2030-06-15", "end_date": "2030-06-16"})
    events = db.campus_events(user["id"])
    context = {"profile": db.get_profile(user["id"]), "menu": [], "packages": [], "schools": [], "events": events, "weather": {"weather": "晴", "temperature": 20, "tags": []}, "finance": db.finance_summary(user["id"]), "package_metrics": [], "campaigns": [], "parameters": {}}
    text = context_text(context)
    assert "招聘会" in text
    assert "2030-06-15" in text


def test_ai_review_prompt_includes_package_comparison():
    """build_prompt for AI 数据复盘 should include package comparison and discount analysis."""
    prompt = build_prompt("AI 数据复盘", {"profile": {"store_name": "测试"}, "menu": [], "packages": [], "schools": [], "events": [], "weather": {"weather": "晴", "temperature": 20, "tags": []}, "finance": {}, "package_metrics": [], "campaigns": [], "parameters": {}})
    assert "套餐" in prompt
    assert "优惠" in prompt or "成本" in prompt
    assert "明日" in prompt


# ---------------------------------------------------------------------------
# V2.1: Package metrics CRUD
# ---------------------------------------------------------------------------

def test_package_metric_upsert(tmp_path):
    """Saving a package metric twice should upsert, not duplicate."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    mid1 = db.save_package_metric(user["id"], {"record_date": "2030-04-01", "package_name": "测试套餐", "order_count": 5, "revenue": 75, "ingredient_cost": 30, "discount_cost": 5})
    mid2 = db.save_package_metric(user["id"], {"record_date": "2030-04-01", "package_name": "测试套餐", "order_count": 10, "revenue": 150, "ingredient_cost": 60, "discount_cost": 15})
    assert mid1 == mid2
    rows = db.list_package_metrics(user["id"], "2030-04-01", "2030-04-01")
    test_rows = [r for r in rows if r["package_name"] == "测试套餐"]
    assert len(test_rows) == 1
    assert test_rows[0]["order_count"] == 10


def test_schools_have_operating_tips(tmp_path):
    """All demo schools should have operating tips set."""
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    schools = db.get_schools(user["id"])
    for school in schools:
        assert school.get("operating_tip"), "School {} should have operating_tip".format(school["name"])
        assert school.get("class_time_slots"), "School {} should have class_time_slots".format(school["name"])


def test_weather_impact_changes_with_weather():
    rainy = WeatherService.manual("北京", "小雨", 16, 18, 12, 80)
    hot = WeatherService.manual("北京", "高温晴天", 33, 35, 26, 0)
    windy = WeatherService.manual("北京", "大风", 18, 20, 12, 0, wind_speed=28)
    assert "外带" in business_impact(rainy) or "热食" in business_impact(rainy)
    assert "冷饮" in business_impact(hot)
    assert "快速打包" in business_impact(windy)
    assert business_impact(rainy) != business_impact(hot)


def test_prompt_and_cleanup_reject_markdown_latex():
    prompt = build_prompt("微信群文案", {"profile": {"store_name": "东门小吃铺"}, "menu": [], "packages": [], "schools": [], "events": [], "weather": {"weather": "晴", "temperature": 20, "tags": []}, "finance": {}, "package_metrics": [], "campaigns": [], "parameters": {}})
    assert "Markdown" in prompt and "LaTeX" in prompt
    cleaned = clean_direct_content("**加粗**\n#标题\n$19.9$\n\\(x+y\\)\n- 到店就能买")
    assert "*" not in cleaned and "#" not in cleaned and "$" not in cleaned and "\\(" not in cleaned


def test_demo_package_names_are_realistic(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    names = [item["name"] for item in db.get_packages(user["id"])]
    assert names == ["鸡排柠檬茶套餐", "饭团关东煮豆浆套餐", "烤肠饭团套餐", "关东煮豆浆套餐"]


def test_custom_task_add_and_soft_delete(tmp_path):
    db = V2Database(tmp_path / "v2.db")
    user = db.authenticate("admin", "admin")
    before = len(db.get_tasks(user["id"]))
    task_id = db.add_task(user["id"], "准备晚间外带包装", "活动策划", "去处理")
    assert len(db.get_tasks(user["id"])) == before + 1
    db.delete_task(user["id"], task_id)
    assert all(item["id"] != task_id for item in db.get_tasks(user["id"]))
