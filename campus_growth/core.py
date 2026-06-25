"""本地存储、认证和 Windows 凭据保护。"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    path = Path(root) if root else Path.home() / "AppData" / "Local"
    path = path / "CampusGrowthAssistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


class SecretProtector:
    """优先使用 Windows DPAPI；非 Windows 环境只用于开发测试。"""

    @staticmethod
    def _blob(data: bytes):
        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = (ctypes.c_byte * len(data))(*data)
        return DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer

    @classmethod
    def protect(cls, value: str) -> str:
        raw = value.encode("utf-8")
        if os.name != "nt":
            return "plain:" + base64.b64encode(raw).decode("ascii")
        try:
            in_blob, _buffer = cls._blob(raw)
            out_blob, _ = cls._blob(b"\x00")
            ok = ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
            )
            if not ok:
                raise ctypes.WinError()
            try:
                encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
        except Exception:
            # 不因系统策略导致整个设置页失效；开发环境降级值仍不在 UI 中展示。
            return "plain:" + base64.b64encode(raw).decode("ascii")

    @classmethod
    def unprotect(cls, value: str) -> str:
        if not value:
            return ""
        prefix, encoded = value.split(":", 1)
        raw = base64.b64decode(encoded)
        if prefix != "dpapi" or os.name != "nt":
            return raw.decode("utf-8")
        in_blob, _buffer = cls._blob(raw)
        out_blob, _ = cls._blob(b"\x00")
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        )
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iteration, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt), int(iteration)
        )
        return secrets.compare_digest(base64.b64encode(digest).decode("ascii"), expected)
    except (ValueError, TypeError):
        return False


class Database:
    """每个 Windows 用户一份 SQLite 数据库。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.data_dir = app_data_dir() if db_path is None else Path(db_path).parent
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path else self.data_dir / "campus_growth.db"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    trial_start_at TEXT
                );
                CREATE TABLE IF NOT EXISTS store_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    store_name TEXT NOT NULL,
                    business_type TEXT NOT NULL,
                    products TEXT NOT NULL,
                    price_range TEXT NOT NULL,
                    city TEXT NOT NULL,
                    address TEXT DEFAULT '',
                    school_name TEXT NOT NULL,
                    target_students TEXT DEFAULT '[]',
                    discount_options TEXT DEFAULT '[]',
                    business_hours TEXT DEFAULT '',
                    channels TEXT DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, setting_key),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS school_calendars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    school_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT DEFAULT '',
                    raw_content TEXT NOT NULL,
                    parsed_summary TEXT DEFAULT '',
                    term_start TEXT DEFAULT '',
                    term_end TEXT DEFAULT '',
                    exam_weeks TEXT DEFAULT '',
                    holidays TEXT DEFAULT '',
                    class_time_slots TEXT DEFAULT '',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS campaign_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    campaign_name TEXT NOT NULL,
                    campaign_plan TEXT NOT NULL,
                    node_tags TEXT DEFAULT '[]',
                    weather_snapshot TEXT DEFAULT '{}',
                    publish_channels TEXT DEFAULT '[]',
                    publish_time TEXT DEFAULT '',
                    coupon_used INTEGER DEFAULT 0,
                    visitor_count INTEGER DEFAULT 0,
                    sales_amount REAL DEFAULT 0,
                    feedback TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS campaign_contents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    campaign_id INTEGER,
                    content_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(campaign_id) REFERENCES campaign_records(id) ON DELETE SET NULL
                );
                """
            )
            exists = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                    ("admin", hash_password("admin"), self.now()),
                )

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode_profile(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        for key in ("target_students", "discount_options", "channels"):
            data[key] = json.loads(data.get(key) or "[]")
        return data

    def create_user(self, username: str, password: str) -> int:
        username = username.strip()
        if len(username) < 3 or len(password) < 4:
            raise ValueError("账号至少 3 位，密码至少 4 位。")
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, hash_password(password), self.now()),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            raise ValueError("该账号已存在。")

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return None
            if not row["trial_start_at"]:
                trial_start = date.today().isoformat()
                conn.execute("UPDATE users SET trial_start_at = ? WHERE id = ?", (trial_start, row["id"]))
                row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return dict(row)

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_trial_status(self, user_id: int) -> Dict[str, Any]:
        user = self.get_user(user_id)
        start = date.fromisoformat(user["trial_start_at"]) if user and user["trial_start_at"] else date.today()
        elapsed = (date.today() - start).days
        return {"start": start.isoformat(), "remaining": max(0, 14 - elapsed), "expired": elapsed >= 14}

    def get_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM store_profiles WHERE user_id = ?", (user_id,)).fetchone()
            return self._decode_profile(row) if row else None

    def save_profile(self, user_id: int, profile: Dict[str, Any]) -> None:
        required = {"store_name": "店铺名称", "business_type": "主营业务", "products": "主要商品或服务", "price_range": "价格范围", "city": "所在城市", "school_name": "附近学校"}
        missing = [label for key, label in required.items() if not str(profile.get(key, "")).strip()]
        if missing:
            raise ValueError("请填写：" + "、".join(missing))
        data = {key: str(profile.get(key, "")).strip() for key in required}
        data.update({"address": str(profile.get("address", "")).strip(), "business_hours": str(profile.get("business_hours", "")).strip()})
        data.update({key: self._json(profile.get(key, [])) for key in ("target_students", "discount_options", "channels")})
        fields = ["store_name", "business_type", "products", "price_range", "city", "address", "school_name", "target_students", "discount_options", "business_hours", "channels"]
        values = [data[key] for key in fields]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO store_profiles(user_id, store_name, business_type, products, price_range, city, address, school_name,
                   target_students, discount_options, business_hours, channels, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET store_name=excluded.store_name, business_type=excluded.business_type,
                   products=excluded.products, price_range=excluded.price_range, city=excluded.city, address=excluded.address,
                   school_name=excluded.school_name, target_students=excluded.target_students,
                   discount_options=excluded.discount_options, business_hours=excluded.business_hours,
                   channels=excluded.channels, updated_at=excluded.updated_at""",
                [user_id] + values + [self.now()],
            )

    def set_setting(self, user_id: int, key: str, value: str, secret: bool = False) -> None:
        stored = SecretProtector.protect(value) if secret else value
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO app_settings(user_id, setting_key, setting_value, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                (user_id, key, stored, self.now()),
            )

    def get_setting(self, user_id: int, key: str, default: str = "", secret: bool = False) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT setting_value FROM app_settings WHERE user_id = ? AND setting_key = ?", (user_id, key)
            ).fetchone()
        if not row:
            return default
        return SecretProtector.unprotect(row["setting_value"]) if secret else row["setting_value"]

    def get_ai_settings(self, user_id: int, include_key: bool = True) -> Dict[str, Any]:
        key = self.get_setting(user_id, "ai_api_key", "", secret=True) if include_key else ""
        return {
            "base_url": self.get_setting(user_id, "ai_base_url", "https://api.openai.com/v1").rstrip("/"),
            "api_key": key,
            "model": self.get_setting(user_id, "ai_model", "gpt-4o-mini"),
            "temperature": float(self.get_setting(user_id, "ai_temperature", "0.7")),
            "max_tokens": int(self.get_setting(user_id, "ai_max_tokens", "2000")),
            "stream": self.get_setting(user_id, "ai_stream", "1") == "1",
        }

    def save_calendar(self, user_id: int, calendar: Dict[str, str]) -> int:
        fields = ["school_name", "source_type", "source_ref", "raw_content", "parsed_summary", "term_start", "term_end", "exam_weeks", "holidays", "class_time_slots"]
        values = [calendar.get(key, "") for key in fields]
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO school_calendars(user_id, school_name, source_type, source_ref, raw_content, parsed_summary, term_start, term_end, exam_weeks, holidays, class_time_slots, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [user_id] + values + [self.now()],
            )
            return int(cursor.lastrowid)

    def get_latest_calendar(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM school_calendars WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1", (user_id,)).fetchone()
            return dict(row) if row else None

    def save_campaign(self, user_id: int, campaign: Dict[str, Any], campaign_id: Optional[int] = None) -> int:
        fields = ["campaign_name", "campaign_plan", "node_tags", "weather_snapshot", "publish_channels", "publish_time", "coupon_used", "visitor_count", "sales_amount", "feedback"]
        data = dict(campaign)
        for key in ("node_tags", "weather_snapshot", "publish_channels"):
            if not isinstance(data.get(key), str):
                data[key] = self._json(data.get(key, [] if key != "weather_snapshot" else {}))
        values = [data.get(key, "") for key in fields]
        with self._connect() as conn:
            if campaign_id:
                conn.execute(
                    "UPDATE campaign_records SET campaign_name=?, campaign_plan=?, node_tags=?, weather_snapshot=?, publish_channels=?, publish_time=?, coupon_used=?, visitor_count=?, sales_amount=?, feedback=?, updated_at=? WHERE id=? AND user_id=?",
                    values + [self.now(), campaign_id, user_id],
                )
                return campaign_id
            cursor = conn.execute(
                "INSERT INTO campaign_records(user_id, campaign_name, campaign_plan, node_tags, weather_snapshot, publish_channels, publish_time, coupon_used, visitor_count, sales_amount, feedback, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [user_id] + values + [self.now(), self.now()],
            )
            return int(cursor.lastrowid)

    def list_campaigns(self, user_id: int, days: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM campaign_records WHERE user_id = ?"
        args: List[Any] = [user_id]
        if days is not None:
            query += " AND date(created_at) >= date('now', ?)"
            args.append("-{} days".format(days - 1))
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["node_tags"] = json.loads(item["node_tags"] or "[]")
            item["publish_channels"] = json.loads(item["publish_channels"] or "[]")
            output.append(item)
        return output

    def save_content(self, user_id: int, content_type: str, content: str, campaign_id: Optional[int] = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO campaign_contents(user_id, campaign_id, content_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, campaign_id, content_type, content, self.now()),
            )
            return int(cursor.lastrowid)

    def save_session(self, user_id: int) -> None:
        payload = {"user_id": user_id, "expires_at": (datetime.now() + timedelta(days=7)).isoformat()}
        (self.data_dir / "session.json").write_text(json.dumps(payload), encoding="utf-8")

    def restore_session(self) -> Optional[int]:
        path = self.data_dir / "session.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if datetime.fromisoformat(payload["expires_at"]) > datetime.now() and self.get_user(int(payload["user_id"])):
                return int(payload["user_id"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        return None

    def clear_session(self) -> None:
        try:
            (self.data_dir / "session.json").unlink()
        except FileNotFoundError:
            pass
