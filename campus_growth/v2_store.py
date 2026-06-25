"""V2 本地数据迁移、校园 Demo 数据与商家运营读写接口。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from campus_growth.core import Database


DEMO_PROFILE = {
    "store_name": "东门小吃铺",
    "business_type": "校园小吃",
    "products": "炸鸡、烤肠、饭团、关东煮、饮品",
    "price_range": "4-20 元",
    "city": "北京",
    "address": "北京市海淀区学院路",
    "school_name": "北京科技大学、北京林业大学、中国地质大学",
    "target_students": ["大学生", "晚自习学生", "社团活动学生", "考试周复习学生"],
    "discount_options": ["校园卡立减 2 元", "套餐优惠", "第二件半价"],
    "business_hours": "10:00 - 23:00",
    "channels": ["微信群", "朋友圈", "小红书"],
    "owner_phone": "138****2026",
    "notes": "晚间 17:30-22:00 是到店高峰，关东煮和热豆浆适合降温天气。",
}

DEMO_MENU = [
    ("香酥炸鸡排", "小吃", 12), ("烤肠", "小吃", 5), ("饭团", "主食", 8),
    ("关东煮三件套", "热食", 10), ("柠檬茶", "饮品", 8), ("热豆浆", "热饮", 4),
]
DEMO_PACKAGES = [
    ("鸡排柠檬茶套餐", "炸鸡排 + 柠檬茶", 18, "晚自习学生"),
    ("饭团关东煮豆浆套餐", "饭团 + 关东煮 + 热豆浆", 20, "考试周复习学生"),
    ("烤肠饭团套餐", "烤肠 + 饭团", 12, "下课学生"),
    ("关东煮豆浆套餐", "关东煮三件套 + 热豆浆", 13, "雨天到店/外带"),
]

PACKAGE_RENAMES = {
    "晚自习续命套餐": "鸡排柠檬茶套餐",
    "考试周能量套餐": "饭团关东煮豆浆套餐",
    "下课快走套餐": "烤肠饭团套餐",
    "雨天暖胃套餐": "关东煮豆浆套餐",
}


def nearby_schools_for_address(address: str) -> List[Dict[str, Any]]:
    """可替换为地图 API 的地址→学校适配器；当前提供可信的 Demo 结构。"""
    if "学院路" in (address or ""):
        return [
            {"name": "北京科技大学", "distance_m": 450, "node": "考试周", "detail": "晚自习与图书馆复习人群增加", "color": "orange", "class_time": "08:00、10:00、12:00、14:00、16:00", "lunch_peak": "11:30-13:10", "evening_peak": "17:20-18:40、20:30-22:00", "operating_tip": "主推饭团、关东煮和热豆浆，20:30 后做晚自习外带。"},
            {"name": "北京林业大学", "distance_m": 780, "node": "正常上课周", "detail": "午间与傍晚下课高峰明显", "color": "green", "class_time": "08:00、09:50、12:00、14:00、16:00", "lunch_peak": "11:40-13:00", "evening_peak": "17:00-18:30", "operating_tip": "烤肠饭团套餐适合午间高峰，提前备好烤肠和饭团。"},
            {"name": "中国地质大学（北京）", "distance_m": 1100, "node": "社团招新", "detail": "傍晚社团活动集中", "color": "blue", "class_time": "08:00、10:10、12:10、14:10、16:20", "lunch_peak": "11:50-13:20", "evening_peak": "17:30-19:00、21:00-22:10", "operating_tip": "社团活动日突出多人套餐与提前预订，晚间适合饮品加购。"},
        ]
    return [
        {"name": "附近大学 A", "distance_m": 600, "node": "正常上课周", "detail": "午间与傍晚下课高峰", "color": "orange", "class_time": "08:00、10:00、12:00、14:00、16:00", "lunch_peak": "11:30-13:00", "evening_peak": "17:00-18:30", "operating_tip": "午间主推快速出餐套餐。"},
        {"name": "附近大学 B", "distance_m": 950, "node": "周末返校高峰", "detail": "适合宿舍拼单与外带", "color": "green", "class_time": "08:30、10:30、12:30、14:30、16:30", "lunch_peak": "12:00-13:20", "evening_peak": "17:30-19:30", "operating_tip": "周末重点做宿舍拼单和外带。"},
        {"name": "附近学院 C", "distance_m": 1300, "node": "社团活动", "detail": "团体套餐需求较多", "color": "blue", "class_time": "08:10、10:10、12:10、14:10、16:10", "lunch_peak": "11:40-13:10", "evening_peak": "17:20-19:00", "operating_tip": "活动时段突出团购与加购饮品。"},
    ]


class V2Database(Database):
    """在 V1 数据库上幂等扩展 V2 表，并提供页面需要的聚合方法。"""

    def __init__(self, db_path: Optional[Path] = None):
        super().__init__(db_path)
        self._init_v2()
        self._migrate_package_names()
        self._seed_admin_once()

    def _init_v2(self) -> None:
        with self._connect() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(store_profiles)")}
            for name in ("owner_phone", "notes"):
                if name not in columns:
                    conn.execute("ALTER TABLE store_profiles ADD COLUMN {} TEXT DEFAULT ''".format(name))
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS menu_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
                    category TEXT NOT NULL, price REAL NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS combo_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
                    items TEXT NOT NULL, price REAL NOT NULL, target_scene TEXT DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS school_infos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
                    address TEXT DEFAULT '', distance_m INTEGER NOT NULL DEFAULT 0,
                    current_node TEXT DEFAULT '正常上课周', node_detail TEXT DEFAULT '', color_key TEXT DEFAULT 'orange',
                    updated_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS campus_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, school_id INTEGER,
                    title TEXT NOT NULL, event_type TEXT NOT NULL, start_date TEXT DEFAULT '', end_date TEXT DEFAULT '',
                    status TEXT DEFAULT 'active', FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(school_id) REFERENCES school_infos(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS daily_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, task_date TEXT NOT NULL,
                    title TEXT NOT NULL, route_name TEXT NOT NULL, action_label TEXT NOT NULL,
                    task_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'todo', sort_order INTEGER DEFAULT 0,
                    UNIQUE(user_id, task_date, task_key), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS daily_finance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, record_date TEXT NOT NULL,
                    revenue REAL NOT NULL DEFAULT 0, ingredient_cost REAL NOT NULL DEFAULT 0,
                    labor_cost REAL NOT NULL DEFAULT 0, promotion_cost REAL NOT NULL DEFAULT 0,
                    discount_cost REAL NOT NULL DEFAULT 0, other_cost REAL NOT NULL DEFAULT 0,
                    visitor_count INTEGER NOT NULL DEFAULT 0, coupon_used INTEGER NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, record_date), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS generated_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, content_kind TEXT NOT NULL,
                    title TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS package_daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, record_date TEXT NOT NULL,
                    package_id INTEGER, package_name TEXT NOT NULL, order_count INTEGER NOT NULL DEFAULT 0,
                    revenue REAL NOT NULL DEFAULT 0, ingredient_cost REAL NOT NULL DEFAULT 0,
                    discount_cost REAL NOT NULL DEFAULT 0, channel TEXT DEFAULT '到店', campaign_id INTEGER,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, record_date, package_name),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(package_id) REFERENCES combo_packages(id) ON DELETE SET NULL,
                    FOREIGN KEY(campaign_id) REFERENCES campaign_records(id) ON DELETE SET NULL
                );
                """
            )
            school_columns = {row[1] for row in conn.execute("PRAGMA table_info(school_infos)")}
            for name in ("class_time_slots", "lunch_peak_slots", "evening_peak_slots", "operating_tip"):
                if name not in school_columns:
                    conn.execute("ALTER TABLE school_infos ADD COLUMN {} TEXT DEFAULT ''".format(name))
            campaign_columns = {row[1] for row in conn.execute("PRAGMA table_info(campaign_records)")}
            for name, definition in (("discount_rule", "TEXT DEFAULT '{}'"), ("package_name", "TEXT DEFAULT ''"), ("publish_window", "TEXT DEFAULT ''")):
                if name not in campaign_columns:
                    conn.execute("ALTER TABLE campaign_records ADD COLUMN {} {}".format(name, definition))

    def _migrate_package_names(self) -> None:
        """Rename early AI-ish demo package names in existing local databases."""
        with self._connect() as conn:
            for old, new in PACKAGE_RENAMES.items():
                conn.execute("UPDATE combo_packages SET name=REPLACE(name, ?, ?), items=REPLACE(items, ?, ?), target_scene=REPLACE(target_scene, ?, ?) WHERE name LIKE ? OR items LIKE ? OR target_scene LIKE ?", (old, new, old, new, old, new, "%{}%".format(old), "%{}%".format(old), "%{}%".format(old)))
                conn.execute("UPDATE package_daily_metrics SET package_name=REPLACE(package_name, ?, ?) WHERE package_name LIKE ?", (old, new, "%{}%".format(old)))
                conn.execute("UPDATE campaign_records SET campaign_name=REPLACE(campaign_name, ?, ?), campaign_plan=REPLACE(campaign_plan, ?, ?), package_name=REPLACE(package_name, ?, ?), discount_rule=REPLACE(discount_rule, ?, ?), feedback=REPLACE(feedback, ?, ?) WHERE campaign_name LIKE ? OR campaign_plan LIKE ? OR package_name LIKE ? OR discount_rule LIKE ? OR feedback LIKE ?", (old, new, old, new, old, new, old, new, old, new, "%{}%".format(old), "%{}%".format(old), "%{}%".format(old), "%{}%".format(old), "%{}%".format(old)))

    def _seed_admin_once(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not row:
            return
        admin_id = int(row["id"])
        if self.get_setting(admin_id, "v2_demo_seeded", "") != "1":
            self.reset_demo_data(admin_id, mark_seeded=True)

    def save_profile(self, user_id: int, profile: Dict[str, Any]) -> None:
        data = dict(profile)
        if not str(data.get("school_name", "")).strip():
            data["school_name"] = "、".join(x["name"] for x in nearby_schools_for_address(data.get("address", "")))
        super().save_profile(user_id, data)
        with self._connect() as conn:
            conn.execute("UPDATE store_profiles SET owner_phone=?, notes=? WHERE user_id=?", (str(data.get("owner_phone", "")).strip(), str(data.get("notes", "")).strip(), user_id))
        self.sync_nearby_schools(user_id, data.get("address", ""))

    def get_menu_items(self, user_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM menu_items WHERE user_id=? ORDER BY sort_order, id", (user_id,))]

    def save_menu_item(self, user_id: int, item: Dict[str, Any], item_id: Optional[int] = None) -> int:
        with self._connect() as conn:
            if item_id:
                conn.execute("UPDATE menu_items SET name=?, category=?, price=?, is_active=? WHERE id=? AND user_id=?", (item["name"], item["category"], float(item["price"]), int(item.get("is_active", 1)), item_id, user_id))
                return item_id
            cursor = conn.execute("INSERT INTO menu_items(user_id,name,category,price,is_active,sort_order,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, item["name"], item["category"], float(item["price"]), int(item.get("is_active", 1)), int(item.get("sort_order", 0)), self.now()))
            return int(cursor.lastrowid)

    def delete_menu_item(self, user_id: int, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM menu_items WHERE id=? AND user_id=?", (item_id, user_id))

    def get_packages(self, user_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM combo_packages WHERE user_id=? ORDER BY id", (user_id,))]

    def save_package(self, user_id: int, package: Dict[str, Any], package_id: Optional[int] = None) -> int:
        with self._connect() as conn:
            if package_id:
                conn.execute("UPDATE combo_packages SET name=?, items=?, price=?, target_scene=?, is_active=? WHERE id=? AND user_id=?", (package["name"], package["items"], float(package["price"]), package.get("target_scene", ""), int(package.get("is_active", 1)), package_id, user_id))
                return package_id
            cursor = conn.execute("INSERT INTO combo_packages(user_id,name,items,price,target_scene,is_active,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, package["name"], package["items"], float(package["price"]), package.get("target_scene", ""), int(package.get("is_active", 1)), self.now()))
            return int(cursor.lastrowid)

    def sync_nearby_schools(self, user_id: int, address: str) -> None:
        schools = nearby_schools_for_address(address)
        with self._connect() as conn:
            conn.execute("DELETE FROM campus_events WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM school_infos WHERE user_id=?", (user_id,))
            for school in schools:
                cursor = conn.execute("INSERT INTO school_infos(user_id,name,address,distance_m,current_node,node_detail,color_key,class_time_slots,lunch_peak_slots,evening_peak_slots,operating_tip,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (user_id, school["name"], address, school["distance_m"], school["node"], school["detail"], school["color"], school.get("class_time", ""), school.get("lunch_peak", ""), school.get("evening_peak", ""), school.get("operating_tip", ""), self.now()))
                conn.execute("INSERT INTO campus_events(user_id,school_id,title,event_type,start_date,end_date,status) VALUES(?,?,?,?,?,?,?)", (user_id, cursor.lastrowid, school["node"], school["node"], date.today().isoformat(), "", "active"))

    def get_schools(self, user_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM school_infos WHERE user_id=? ORDER BY distance_m", (user_id,))]

    def update_school(self, user_id: int, school_id: int, data: Dict[str, Any]) -> None:
        fields = ("current_node", "node_detail", "class_time_slots", "lunch_peak_slots", "evening_peak_slots", "operating_tip")
        values = [str(data.get(field, "")).strip() for field in fields]
        with self._connect() as conn:
            conn.execute("UPDATE school_infos SET current_node=?, node_detail=?, class_time_slots=?, lunch_peak_slots=?, evening_peak_slots=?, operating_tip=?, updated_at=? WHERE id=? AND user_id=?", values + [self.now(), school_id, user_id])

    def save_campaign(self, user_id: int, campaign: Dict[str, Any], campaign_id: Optional[int] = None) -> int:
        campaign_id = super().save_campaign(user_id, campaign, campaign_id)
        discount_rule = campaign.get("discount_rule", {})
        if not isinstance(discount_rule, str):
            discount_rule = self._json(discount_rule)
        with self._connect() as conn:
            conn.execute("UPDATE campaign_records SET discount_rule=?, package_name=?, publish_window=? WHERE id=? AND user_id=?", (discount_rule, str(campaign.get("package_name", "")), str(campaign.get("publish_window", campaign.get("publish_time", ""))), campaign_id, user_id))
        return campaign_id

    def list_campaigns(self, user_id: int, days: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        query, args = "SELECT * FROM campaign_records WHERE user_id=?", [user_id]
        if start_date:
            query += " AND date(created_at)>=date(?)"; args.append(start_date)
        elif days is not None:
            query += " AND date(created_at)>=date('now', ?)"; args.append("-{} days".format(days - 1))
        if end_date:
            query += " AND date(created_at)<=date(?)"; args.append(end_date)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["node_tags"] = json.loads(item.get("node_tags") or "[]")
            item["publish_channels"] = json.loads(item.get("publish_channels") or "[]")
            try: item["discount_rule"] = json.loads(item.get("discount_rule") or "{}")
            except json.JSONDecodeError: item["discount_rule"] = {}
            result.append(item)
        return result

    def save_package_metric(self, user_id: int, metric: Dict[str, Any], metric_id: Optional[int] = None) -> int:
        record_date = metric.get("record_date") or date.today().isoformat()
        package_name = str(metric.get("package_name", "")).strip()
        if not package_name:
            raise ValueError("请选择套餐。")
        values = [metric.get(key, 0) for key in ("order_count", "revenue", "ingredient_cost", "discount_cost")]
        values = [int(values[0]), float(values[1]), float(values[2]), float(values[3])]
        with self._connect() as conn:
            if metric_id:
                conn.execute("UPDATE package_daily_metrics SET record_date=?,package_id=?,package_name=?,order_count=?,revenue=?,ingredient_cost=?,discount_cost=?,channel=?,campaign_id=?,updated_at=? WHERE id=? AND user_id=?", [record_date, metric.get("package_id"), package_name] + values + [metric.get("channel", "到店"), metric.get("campaign_id"), self.now(), metric_id, user_id])
                return metric_id
            cursor = conn.execute("INSERT INTO package_daily_metrics(user_id,record_date,package_id,package_name,order_count,revenue,ingredient_cost,discount_cost,channel,campaign_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,record_date,package_name) DO UPDATE SET order_count=excluded.order_count,revenue=excluded.revenue,ingredient_cost=excluded.ingredient_cost,discount_cost=excluded.discount_cost,channel=excluded.channel,campaign_id=excluded.campaign_id,updated_at=excluded.updated_at", [user_id, record_date, metric.get("package_id"), package_name] + values + [metric.get("channel", "到店"), metric.get("campaign_id"), self.now(), self.now()])
            row = conn.execute("SELECT id FROM package_daily_metrics WHERE user_id=? AND record_date=? AND package_name=?", (user_id, record_date, package_name)).fetchone()
            return int(row["id"])

    def delete_package_metric(self, user_id: int, metric_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM package_daily_metrics WHERE id=? AND user_id=?", (metric_id, user_id))

    def list_package_metrics(self, user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        query, args = "SELECT * FROM package_daily_metrics WHERE user_id=?", [user_id]
        if start_date: query += " AND record_date>=?"; args.append(start_date)
        if end_date: query += " AND record_date<=?"; args.append(end_date)
        query += " ORDER BY record_date, package_name"
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(query, args)]
        for row in rows:
            row["gross_profit"] = round(float(row["revenue"]) - float(row["ingredient_cost"]) - float(row["discount_cost"]), 2)
            row["coupon_rate"] = round(float(row["discount_cost"]) / float(row["revenue"]) * 100, 1) if row["revenue"] else 0
        return rows

    def package_summary(self, user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.list_package_metrics(user_id, start_date, end_date)
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(row["package_name"], {"package_name": row["package_name"], "order_count": 0, "revenue": 0.0, "ingredient_cost": 0.0, "discount_cost": 0.0, "gross_profit": 0.0})
            for field in ("order_count", "revenue", "ingredient_cost", "discount_cost", "gross_profit"): item[field] += row[field]
        result = list(grouped.values())
        for item in result:
            item["coupon_rate"] = round(item["discount_cost"] / item["revenue"] * 100, 1) if item["revenue"] else 0
        return sorted(result, key=lambda item: item["revenue"], reverse=True)

    def add_campus_event(self, user_id: int, event: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO campus_events(user_id,school_id,title,event_type,start_date,end_date,status) VALUES(?,?,?,?,?,?,?)", (user_id, event.get("school_id"), event["title"], event.get("event_type", event["title"]), event.get("start_date", date.today().isoformat()), event.get("end_date", ""), "active"))
            return int(cursor.lastrowid)

    def campus_events(self, user_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT e.*, s.name AS school_name FROM campus_events e LEFT JOIN school_infos s ON s.id=e.school_id WHERE e.user_id=? AND e.status='active' ORDER BY e.id DESC", (user_id,))]

    def ensure_daily_tasks(self, user_id: int, target_date: Optional[str] = None) -> None:
        target_date = target_date or date.today().isoformat()
        tasks = [
            ("generate_campaign", "生成今日促销方案", "活动策划", "一键生成"),
            ("post_moments", "发布一条朋友圈促销文案", "内容生成", "去发布"),
            ("post_group", "发布一条微信群活动通知", "内容生成", "去发布"),
            ("record_finance", "记录今日收入和成本", "数据分析", "去记录"),
            ("reply_review", "回复今日顾客评论", "评论回复", "去回复"),
            ("review_yesterday", "查看昨日活动效果", "数据分析", "去查看"),
        ]
        with self._connect() as conn:
            for order, (task_key, title, route, action) in enumerate(tasks):
                conn.execute("INSERT OR IGNORE INTO daily_tasks(user_id,task_date,title,route_name,action_label,task_key,status,sort_order) VALUES(?,?,?,?,?,?,?,?)", (user_id, target_date, title, route, action, task_key, "todo", order))

    def get_tasks(self, user_id: int, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        target_date = target_date or date.today().isoformat()
        self.ensure_daily_tasks(user_id, target_date)
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM daily_tasks WHERE user_id=? AND task_date=? AND status!='removed' ORDER BY sort_order", (user_id, target_date))]

    def add_task(self, user_id: int, title: str, route_name: str = "Dashboard", action_label: str = "去处理", target_date: Optional[str] = None) -> int:
        target_date = target_date or date.today().isoformat()
        title = str(title or "").strip()
        if not title:
            raise ValueError("任务标题不能为空。")
        route_name = route_name if route_name in ("Dashboard", "内容生成", "活动策划", "数据分析", "评论回复", "设置") else "Dashboard"
        action_label = str(action_label or "去处理").strip()
        task_key = "custom_{}_{}".format(target_date.replace("-", ""), abs(hash((title, self.now()))))
        with self._connect() as conn:
            current_max = conn.execute("SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM daily_tasks WHERE user_id=? AND task_date=?", (user_id, target_date)).fetchone()["max_order"]
            cursor = conn.execute(
                "INSERT INTO daily_tasks(user_id,task_date,title,route_name,action_label,task_key,status,sort_order) VALUES(?,?,?,?,?,?,?,?)",
                (user_id, target_date, title, route_name, action_label, task_key, "todo", int(current_max) + 1),
            )
            return int(cursor.lastrowid)

    def delete_task(self, user_id: int, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE daily_tasks SET status='removed' WHERE id=? AND user_id=?", (task_id, user_id))

    def set_task_status(self, user_id: int, task_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE daily_tasks SET status=? WHERE id=? AND user_id=?", (status, task_id, user_id))

    def complete_task_key(self, user_id: int, task_key: str) -> None:
        self.ensure_daily_tasks(user_id)
        with self._connect() as conn:
            conn.execute("UPDATE daily_tasks SET status='done' WHERE user_id=? AND task_date=? AND task_key=? AND status!='removed'", (user_id, date.today().isoformat(), task_key))

    def save_generated(self, user_id: int, kind: str, title: str, content: str, source: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO generated_history(user_id,content_kind,title,content,source,created_at) VALUES(?,?,?,?,?,?)", (user_id, kind, title, content, source, self.now()))
            return int(cursor.lastrowid)

    def generated_history(self, user_id: int, limit: int = 12) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM generated_history WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))]

    def save_finance(self, user_id: int, record: Dict[str, Any], record_id: Optional[int] = None) -> int:
        values = [record.get(key, 0) for key in ("revenue", "ingredient_cost", "labor_cost", "promotion_cost", "discount_cost", "other_cost", "visitor_count", "coupon_used")]
        values = [float(x) if index < 6 else int(x) for index, x in enumerate(values)]
        record_date = record.get("record_date") or date.today().isoformat()
        with self._connect() as conn:
            if record_id:
                conn.execute("UPDATE daily_finance_records SET record_date=?,revenue=?,ingredient_cost=?,labor_cost=?,promotion_cost=?,discount_cost=?,other_cost=?,visitor_count=?,coupon_used=?,note=?,updated_at=? WHERE id=? AND user_id=?", [record_date] + values + [record.get("note", ""), self.now(), record_id, user_id])
                return record_id
            cursor = conn.execute("INSERT INTO daily_finance_records(user_id,record_date,revenue,ingredient_cost,labor_cost,promotion_cost,discount_cost,other_cost,visitor_count,coupon_used,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", [user_id, record_date] + values + [record.get("note", ""), self.now(), self.now()])
            return int(cursor.lastrowid)

    def delete_finance(self, user_id: int, record_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM daily_finance_records WHERE id=? AND user_id=?", (record_id, user_id))

    @staticmethod
    def _finance_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
        cost = sum(float(row.get(key, 0) or 0) for key in ("ingredient_cost", "labor_cost", "promotion_cost", "discount_cost", "other_cost"))
        revenue = float(row.get("revenue", 0) or 0); visitors = int(row.get("visitor_count", 0) or 0); coupons = int(row.get("coupon_used", 0) or 0)
        row.update({"total_cost": round(cost, 2), "gross_profit": round(revenue - cost, 2), "gross_margin": round((revenue - cost) / revenue * 100, 1) if revenue else 0, "avg_ticket": round(revenue / visitors, 2) if visitors else 0, "cost_per_customer": round(cost / visitors, 2) if visitors else 0, "coupon_rate": round(coupons / visitors * 100, 1) if visitors else 0})
        return row

    def list_finance(self, user_id: int, days: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        query, args = "SELECT * FROM daily_finance_records WHERE user_id=?", [user_id]
        if start_date:
            query += " AND record_date>=?"; args.append(start_date)
        elif days:
            query += " AND record_date >= date('now', ?)"; args.append("-{} days".format(days - 1))
        if end_date:
            query += " AND record_date<=?"; args.append(end_date)
        query += " ORDER BY record_date"
        with self._connect() as conn:
            rows = [self._finance_metrics(dict(row)) for row in conn.execute(query, args)]
        return rows

    def finance_summary(self, user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None, days: Optional[int] = 7) -> Dict[str, Any]:
        rows = self.list_finance(user_id, days if not start_date else None, start_date, end_date)
        totals = {"revenue": sum(x["revenue"] for x in rows), "total_cost": sum(x["total_cost"] for x in rows), "gross_profit": sum(x["gross_profit"] for x in rows), "visitors": sum(x["visitor_count"] for x in rows), "coupons": sum(x["coupon_used"] for x in rows)}
        totals["gross_margin"] = round(totals["gross_profit"] / totals["revenue"] * 100, 1) if totals["revenue"] else 0
        latest, previous = (rows[-1], rows[-2]) if len(rows) >= 2 else ({}, {})
        totals["revenue_change"] = round(latest.get("revenue", 0) - previous.get("revenue", 0), 2)
        totals["latest"] = latest; totals["rows"] = rows
        return totals

    def reset_demo_data(self, user_id: int, mark_seeded: bool = False) -> None:
        with self._connect() as conn:
            for table in ("menu_items", "combo_packages", "school_infos", "campus_events", "daily_tasks", "daily_finance_records", "package_daily_metrics", "generated_history", "campaign_contents", "campaign_records"):
                conn.execute("DELETE FROM {} WHERE user_id=?".format(table), (user_id,))
        self.save_profile(user_id, DEMO_PROFILE)
        for index, (name, category, price) in enumerate(DEMO_MENU):
            self.save_menu_item(user_id, {"name": name, "category": category, "price": price, "sort_order": index})
        for name, items, price, scene in DEMO_PACKAGES:
            self.save_package(user_id, {"name": name, "items": items, "price": price, "target_scene": scene})
        today = date.today()
        finance = [(680, 210, 90, 18, 28, 12, 52, 8), (735, 235, 90, 22, 34, 12, 57, 10), (690, 218, 90, 15, 25, 10, 50, 7), (820, 265, 95, 30, 46, 15, 65, 14), (880, 280, 95, 35, 50, 18, 70, 16), (760, 240, 90, 20, 36, 12, 58, 10), (920, 295, 100, 42, 55, 20, 74, 18)]
        notes = ["午间下课高峰稳定", "雨天外带增加", "常规工作日", "考试周晚间套餐有效", "社团活动带动拼单", "天气转凉热饮增加", "考试周 + 雨天表现最佳"]
        for index, values in enumerate(finance):
            day = (today - timedelta(days=6-index)).isoformat()
            self.save_finance(user_id, {"record_date": day, "revenue": values[0], "ingredient_cost": values[1], "labor_cost": values[2], "promotion_cost": values[3], "discount_cost": values[4], "other_cost": values[5], "visitor_count": values[6], "coupon_used": values[7], "note": notes[index]})
        package_ids = {item["name"]: item["id"] for item in self.get_packages(user_id)}
        package_metrics = [
            ("鸡排柠檬茶套餐", 12, 216, 88, 18, "到店"), ("烤肠饭团套餐", 15, 180, 70, 12, "到店"),
            ("饭团关东煮豆浆套餐", 14, 280, 118, 22, "到店"), ("关东煮豆浆套餐", 16, 208, 82, 24, "外带"),
            ("饭团关东煮豆浆套餐", 19, 380, 162, 32, "到店"), ("鸡排柠檬茶套餐", 17, 306, 122, 24, "到店"),
            ("鸡排柠檬茶套餐", 8, 144, 58, 10, "外带"), ("烤肠饭团套餐", 11, 132, 52, 8, "到店"),
            ("关东煮豆浆套餐", 23, 299, 118, 36, "外带"), ("饭团关东煮豆浆套餐", 21, 420, 176, 34, "到店"),
            ("烤肠饭团套餐", 18, 216, 84, 16, "到店"), ("关东煮豆浆套餐", 14, 182, 72, 22, "到店"),
        ]
        # Map each metric to a day index (0=oldest, 6=today) for even distribution
        metric_days = [0, 0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6]
        for index, values in enumerate(package_metrics):
            day = (today - timedelta(days=6 - metric_days[index])).isoformat()
            self.save_package_metric(user_id, {"record_date": day, "package_id": package_ids.get(values[0]), "package_name": values[0], "order_count": values[1], "revenue": values[2], "ingredient_cost": values[3], "discount_cost": values[4], "channel": values[5]})
        self.ensure_daily_tasks(user_id)
        campaigns_data = [
            {"campaign_name": "饭团关东煮豆浆套餐", "campaign_plan": "主推饭团+关东煮+热豆浆，晚间学生凭校园卡立减2元。17:30和20:30两个高峰时段集中发布，覆盖晚自习前后人群。", "node_tags": ["考试周"], "weather_snapshot": {"weather": "多云"}, "publish_channels": ["微信群", "朋友圈"], "coupon_used": 22, "visitor_count": 74, "sales_amount": 920, "feedback": "考试周转化率高，晚间套餐核销占整体 60%", "discount_rule": {"type": "立减", "value": 2, "threshold": 0, "scope": "套餐｜饭团关东煮豆浆套餐", "window": "17:30-22:00", "stackable": False, "gift": "", "description": "立减 2 元，适用 套餐｜饭团关东煮豆浆套餐，时段 17:30-22:00，不叠加"}, "package_name": "饭团关东煮豆浆套餐", "publish_window": "17:30-22:00"},
            {"campaign_name": "关东煮豆浆套餐", "campaign_plan": "关东煮三件套+热豆浆，覆盖17:30和20:30高峰。雨天外带比例高，备好防烫袋和一次性杯盖。", "node_tags": ["雨天"], "weather_snapshot": {"weather": "小雨"}, "publish_channels": ["微信群", "朋友圈", "小红书"], "coupon_used": 18, "visitor_count": 58, "sales_amount": 760, "feedback": "雨天外带占比 65%，热食套餐好评率高", "discount_rule": {"type": "折扣", "value": 8.5, "threshold": 0, "scope": "套餐｜关东煮豆浆套餐", "window": "17:30-20:30", "stackable": False, "gift": "", "description": "8.5 折，适用 套餐｜关东煮豆浆套餐，时段 17:30-20:30，不叠加"}, "package_name": "关东煮豆浆套餐", "publish_window": "17:30-20:30"},
            {"campaign_name": "烤肠饭团套餐", "campaign_plan": "烤肠+饭团，午间高峰快速出餐。主打 11:30-13:30 下课人流，提前备好 20 份烤肠和饭团。", "node_tags": ["正常上课周"], "weather_snapshot": {"weather": "晴"}, "publish_channels": ["微信群"], "coupon_used": 12, "visitor_count": 45, "sales_amount": 540, "feedback": "午间下课高峰快速出餐，客单价低但走量快", "discount_rule": {"type": "固定套餐价", "value": 10, "threshold": 0, "scope": "套餐｜烤肠饭团套餐", "window": "11:30-13:30", "stackable": False, "gift": "", "description": "固定套餐价 10 元，适用 套餐｜烤肠饭团套餐，时段 11:30-13:30，不叠加"}, "package_name": "烤肠饭团套餐", "publish_window": "11:30-13:30"},
        ]
        for campaign_data in campaigns_data:
            self.save_campaign(user_id, campaign_data)
        if mark_seeded:
            self.set_setting(user_id, "v2_demo_seeded", "1")
