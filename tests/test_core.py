import sqlite3

from campus_growth.core import Database


def profile():
    return {
        "store_name": "东门柠檬茶", "business_type": "奶茶", "products": "柠檬茶、奶茶",
        "price_range": "12-25 元", "city": "北京", "address": "东门 50 米",
        "school_name": "示例大学", "target_students": ["本科生"],
        "discount_options": ["第二杯半价"], "business_hours": "10:00-22:00", "channels": ["微信群", "朋友圈"],
    }


def test_default_login_profile_and_campaign(tmp_path):
    db = Database(tmp_path / "test.db")
    user = db.authenticate("admin", "admin")
    assert user and user["username"] == "admin"
    assert db.authenticate("admin", "wrong") is None
    assert db.get_trial_status(user["id"])["remaining"] == 14
    db.save_profile(user["id"], profile())
    saved = db.get_profile(user["id"])
    assert saved["store_name"] == "东门柠檬茶"
    assert saved["channels"] == ["微信群", "朋友圈"]
    campaign_id = db.save_campaign(user["id"], {"campaign_name": "期末续命", "campaign_plan": "活动名称：期末续命", "node_tags": ["考试周"], "weather_snapshot": {"weather": "小雨"}, "publish_channels": ["微信群"], "coupon_used": 3, "visitor_count": 8, "sales_amount": 120})
    records = db.list_campaigns(user["id"], days=7)
    assert records[0]["id"] == campaign_id
    assert records[0]["node_tags"] == ["考试周"]


def test_secret_setting_does_not_store_raw_value(tmp_path):
    db = Database(tmp_path / "test.db")
    user = db.authenticate("admin", "admin")
    db.set_setting(user["id"], "ai_api_key", "secret-demo-key", secret=True)
    assert db.get_setting(user["id"], "ai_api_key", secret=True) == "secret-demo-key"
    connection = sqlite3.connect(str(tmp_path / "test.db"))
    raw = connection.execute("SELECT setting_value FROM app_settings WHERE setting_key='ai_api_key'").fetchone()[0]
    connection.close()
    assert raw != "secret-demo-key"
