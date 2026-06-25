"""校园商家 AI 增长助理 V2：暖橙 SaaS 风格商家运营后台。"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

import pyqtgraph as pg
from PyQt5.QtCore import QDate, QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from campus_growth import APP_NAME
from campus_growth.ai_service import AIService
from campus_growth.services.client import AIClient
from campus_growth.services.weather import WeatherService, business_impact
from campus_growth.v2_store import DEMO_PROFILE, V2Database


STYLE = """
* { font-family: 'Microsoft YaHei UI', 'Segoe UI'; }
QMainWindow, QDialog { background: #F7F8FC; color: #172033; }
QWidget#contentArea { background: #F7F8FC; }
QFrame#sidebar { background: #151C2B; }
QLabel#brand { color: white; font-size: 20px; font-weight: 800; }
QLabel#brandSub { color: #A8B2C7; font-size: 11px; }
QLabel#pageTitle { color: #172033; font-size: 25px; font-weight: 800; }
QLabel#pageSubtitle, QLabel#muted { color: #7C879D; }
QLabel#metricValue { color: #172033; font-size: 24px; font-weight: 800; }
QLabel#metricLabel { color: #8A94A8; font-size: 11px; }
QLabel#badgeOrange { color: #C2410C; background: #FFF0E8; border-radius: 9px; padding: 3px 8px; font-weight: 700; }
QLabel#badgeGreen { color: #15803D; background: #EAF8EF; border-radius: 9px; padding: 3px 8px; font-weight: 700; }
QLabel#badgeBlue { color: #2563EB; background: #EDF4FF; border-radius: 9px; padding: 3px 8px; font-weight: 700; }
QLabel#badgeGray { color: #64748B; background: #F1F5F9; border-radius: 9px; padding: 3px 8px; }
QFrame#card { background: white; border: 1px solid #EDF0F5; border-radius: 14px; }
QFrame#hero { background: #FFF4EC; border: 1px solid #FFD4B6; border-radius: 14px; }
QListWidget#navigation { background: #151C2B; color: #C7D0E1; border: none; outline: none; padding: 8px; }
QListWidget#navigation::item { padding: 11px 12px; margin: 2px 0; border-radius: 8px; }
QListWidget#navigation::item:selected { background: #F97316; color: white; font-weight: 700; }
QListWidget#navigation::item:hover { background: #263149; }
QPushButton { background: #F97316; color: white; border: none; border-radius: 8px; padding: 8px 13px; font-weight: 700; }
QPushButton:hover { background: #EA580C; }
QPushButton:disabled { background: #FDBA8C; color: #FFF7ED; }
QPushButton[variant="secondary"] { background: #FFF1E8; color: #D9530D; }
QPushButton[variant="secondary"]:hover { background: #FFE0CB; }
QPushButton[variant="ghost"] { background: #F4F6FA; color: #526079; }
QPushButton[variant="danger"] { background: #FEECEC; color: #DC2626; }
QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #DDE3ED; border-radius: 8px; padding: 7px; min-height: 18px; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #F97316; }
QCheckBox { color: #42526B; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #CBD5E1; border-radius: 5px; background: white; }
QCheckBox::indicator:checked { background: #F97316; border-color: #F97316; }
QTableWidget { background: white; border: 1px solid #EDF0F5; border-radius: 10px; gridline-color: #F0F2F6; }
QHeaderView::section { background: #F8FAFC; color: #64748B; border: none; padding: 8px; font-weight: 700; }
QTabWidget::pane { border: 1px solid #EDF0F5; background: white; border-radius: 10px; }
QTabBar::tab { background: #F4F6FA; color: #64748B; padding: 8px 14px; margin-right: 3px; border-top-left-radius: 7px; border-top-right-radius: 7px; }
QTabBar::tab:selected { background: #FFF1E8; color: #D9530D; font-weight: 700; }
QScrollArea { border: none; }
"""


def button(text: str, variant: str = "primary") -> QPushButton:
    item = QPushButton(text)
    if variant != "primary":
        item.setProperty("variant", variant)
    return item


def badge(text: str, kind: str = "orange") -> QLabel:
    item = QLabel(text); item.setObjectName("badge" + kind.capitalize()); item.setAlignment(Qt.AlignCenter)
    return item


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(); frame.setObjectName("card")
    layout = QVBoxLayout(frame); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(10)
    return frame, layout


def title_block(title: str, subtitle: str) -> QWidget:
    widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 8); layout.setSpacing(3)
    head = QLabel(title); head.setObjectName("pageTitle"); layout.addWidget(head)
    sub = QLabel(subtitle); sub.setObjectName("pageSubtitle"); layout.addWidget(sub)
    return widget


def copy_to_clipboard(value: str) -> None:
    QApplication.clipboard().setText(value)


def _safe_float(value) -> float:
    """Coerce a DB value to float, defaulting to 0 for empty/missing."""
    try:
        return float(value) if value not in (None, "") else 0.0
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value) -> int:
    """Coerce a DB value to int, defaulting to 0 for empty/missing."""
    try:
        return int(float(value)) if value not in (None, "") else 0
    except (ValueError, TypeError):
        return 0


class Worker(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    def __init__(self, fn: Callable[[], Any]): super().__init__(); self.fn = fn
    @pyqtSlot()
    def run(self):
        try: self.done.emit(self.fn())
        except Exception as exc: self.failed.emit(str(exc))


class LoginDialog(QDialog):
    def __init__(self, db: V2Database):
        super().__init__(); self.db, self.user = db, None
        self.setWindowTitle(APP_NAME); self.setMinimumSize(430, 420)
        layout = QVBoxLayout(self); layout.setContentsMargins(38, 34, 38, 34); layout.setSpacing(14)
        mark = QLabel("🍢"); mark.setAlignment(Qt.AlignCenter); mark.setStyleSheet("font-size:42px;"); layout.addWidget(mark)
        title = QLabel("校园商家 AI 增长助理"); title.setObjectName("pageTitle"); title.setAlignment(Qt.AlignCenter); layout.addWidget(title)
        hint = QLabel("用天气、校园节点和 AI，帮小店每天多卖一点。\n演示账号：admin / admin"); hint.setObjectName("muted"); hint.setAlignment(Qt.AlignCenter); layout.addWidget(hint)
        form = QFormLayout(); form.setSpacing(10)
        self.username, self.password = QLineEdit("admin"), QLineEdit("admin"); self.password.setEchoMode(QLineEdit.Password)
        form.addRow("账号", self.username); form.addRow("密码", self.password); layout.addLayout(form)
        self.remember = QCheckBox("7 天内保持登录"); self.remember.setChecked(True); layout.addWidget(self.remember)
        login = button("登录并进入工作台"); register = button("注册本地账号", "secondary")
        login.clicked.connect(self.login); register.clicked.connect(self.register); layout.addWidget(login); layout.addWidget(register); layout.addStretch()
    def login(self):
        user = self.db.authenticate(self.username.text(), self.password.text())
        if not user: return QMessageBox.warning(self, "登录失败", "账号或密码错误。")
        self.user = user
        self.db.save_session(user["id"]) if self.remember.isChecked() else self.db.clear_session()
        self.accept()
    def register(self):
        try:
            self.db.create_user(self.username.text(), self.password.text())
            self.user = self.db.authenticate(self.username.text(), self.password.text())
            self.db.save_session(self.user["id"]); self.accept()
        except ValueError as exc: QMessageBox.warning(self, "无法注册", str(exc))


class ProfileEditor(QWidget):
    def __init__(self, profile: Optional[Dict[str, Any]] = None, compact: bool = False):
        super().__init__(); self.fields: Dict[str, Any] = {}; data = profile or {}
        form = QFormLayout(self); form.setLabelAlignment(Qt.AlignRight); form.setSpacing(9)
        specs = [("store_name", "店铺名称 *"), ("business_type", "主营业务 *"), ("products", "商品/服务 *"), ("price_range", "价格范围 *"), ("city", "所在城市 *"), ("address", "店铺地址 *"), ("school_name", "附近学校"), ("business_hours", "营业时间"), ("owner_phone", "老板手机号"), ("target_students", "目标客群"), ("channels", "常用渠道"), ("discount_options", "常用优惠")]
        if compact: specs = specs[:8]
        for key, label in specs:
            raw = data.get(key, ""); value = "，".join(raw) if isinstance(raw, list) else str(raw or "")
            field = QLineEdit(value); self.fields[key] = field; form.addRow(label, field)
        if not compact:
            notes = QPlainTextEdit(str(data.get("notes", ""))); notes.setFixedHeight(60); self.fields["notes"] = notes; form.addRow("经营备注", notes)
    def values(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        multi = {"target_students", "channels", "discount_options"}
        for key, widget in self.fields.items():
            raw = widget.toPlainText().strip() if isinstance(widget, QPlainTextEdit) else widget.text().strip()
            result[key] = [x.strip() for x in raw.replace("、", "，").replace(",", "，").split("，") if x.strip()] if key in multi else raw
        return result


class OnboardingDialog(QDialog):
    def __init__(self, window):
        super().__init__(window); self.window = window; self.setWindowTitle("欢迎，先配置你的小店"); self.setMinimumSize(620, 610)
        layout = QVBoxLayout(self); layout.addWidget(title_block("先告诉我你的店铺情况", "完成后，AI 才能生成真正适合你的活动和文案。"))
        self.editor = ProfileEditor(); layout.addWidget(self.editor)
        use_demo = button("填入东门小吃铺示例", "secondary"); use_demo.clicked.connect(self.fill_demo); layout.addWidget(use_demo)
        actions = QDialogButtonBox(QDialogButtonBox.Save); actions.accepted.connect(self.save); layout.addWidget(actions)
    def fill_demo(self):
        self.editor = self._replace_editor(self.editor, DEMO_PROFILE)
    def _replace_editor(self, old, data):
        layout = self.layout(); index = layout.indexOf(old); old.setParent(None); editor = ProfileEditor(data); layout.insertWidget(index, editor); return editor
    def save(self):
        try:
            self.window.db.save_profile(self.window.user_id, self.editor.values()); self.window.refresh_all(); self.accept()
        except ValueError as exc: QMessageBox.warning(self, "请补充信息", str(exc))


class ManualWeatherDialog(QDialog):
    def __init__(self, city: str):
        super().__init__(); self.setWindowTitle("手动更新天气")
        form = QFormLayout(self); self.weather = QLineEdit("小雨")
        self.temp, self.high, self.low, self.precip = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for box, value in ((self.temp, 16), (self.high, 18), (self.low, 11), (self.precip, 75)):
            box.setRange(-50, 100); box.setValue(value)
        form.addRow("城市", QLabel(city)); form.addRow("天气", self.weather); form.addRow("当前温度", self.temp); form.addRow("最高温", self.high); form.addRow("最低温", self.low); form.addRow("降水概率", self.precip)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def value(self, city: str): return WeatherService.manual(city, self.weather.text(), self.temp.value(), self.high.value(), self.low.value(), self.precip.value())


class TaskDialog(QDialog):
    def __init__(self, window):
        super().__init__(window); self.setWindowTitle("新增今日任务"); self.setMinimumWidth(420)
        form = QFormLayout(self); self.title = QLineEdit(); self.title.setPlaceholderText("例如：准备 30 份晚间外带套餐")
        self.route = QComboBox(); self.route.addItems(("Dashboard", "内容生成", "活动策划", "数据分析", "评论回复", "设置"))
        self.action = QLineEdit("去处理")
        form.addRow("任务内容", self.title); form.addRow("点击后跳转", self.route); form.addRow("按钮文案", self.action)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def values(self):
        return {"title": self.title.text().strip(), "route_name": self.route.currentText(), "action_label": self.action.text().strip() or "去处理"}


class Page(QWidget):
    def __init__(self, window):
        super().__init__(); self.window = window
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); outer.addWidget(scroll)
        self.body = QWidget(); self.body.setObjectName("contentArea"); self.layout = QVBoxLayout(self.body); self.layout.setContentsMargins(28, 22, 28, 32); self.layout.setSpacing(16); scroll.setWidget(self.body)
    def refresh(self): pass


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, hint: str, accent: str = "orange"):
        super().__init__(); self.setObjectName("card"); self.setMinimumHeight(108)
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 13, 16, 13); layout.setSpacing(3)
        top = QHBoxLayout(); label_widget = QLabel(label); label_widget.setObjectName("metricLabel"); top.addWidget(label_widget); top.addStretch(); top.addWidget(badge("●", accent)); layout.addLayout(top)
        self.value = QLabel(value); self.value.setObjectName("metricValue"); layout.addWidget(self.value)
        self.hint = QLabel(hint); self.hint.setObjectName("muted"); layout.addWidget(self.hint)


class DashboardPage(Page):
    def __init__(self, window):
        super().__init__(window)
        self.layout.addWidget(title_block("今天店里该做什么？", "根据今日天气、经营数据和任务清单，快速决定今天怎么卖。"))
        self.metrics_grid = QGridLayout(); self.metrics_grid.setSpacing(12); self.layout.addLayout(self.metrics_grid)
        self.revenue_card, self.visitor_card, self.profit_card, self.trial_card = (MetricCard("今日收入", "--", "近 7 日趋势", "orange"), MetricCard("今日到店", "--", "优惠核销 --", "blue"), MetricCard("今日毛利", "--", "毛利率 --", "green"), MetricCard("试用状态", "--", "全部功能可用", "orange"))
        for i, widget in enumerate((self.revenue_card, self.visitor_card, self.profit_card, self.trial_card)): self.metrics_grid.addWidget(widget, 0, i)
        row = QGridLayout(); row.setSpacing(16); self.layout.addLayout(row)
        weather_frame, weather_box = card(); weather_frame.setObjectName("hero"); row.addWidget(weather_frame, 0, 0, 1, 2)
        head = QHBoxLayout(); head.addWidget(QLabel("🌦  今日天气与经营影响")); head.addStretch(); self.weather_source = badge("演示天气", "orange"); head.addWidget(self.weather_source); weather_box.addLayout(head)
        self.weather_main = QLabel(); self.weather_main.setStyleSheet("font-size:20px;font-weight:800;color:#9A3412;"); weather_box.addWidget(self.weather_main)
        self.weather_date = QLabel(); self.weather_date.setObjectName("muted"); weather_box.addWidget(self.weather_date)
        self.weather_tip = QLabel(); self.weather_tip.setWordWrap(True); self.weather_tip.setObjectName("muted"); weather_box.addWidget(self.weather_tip)
        weather_actions = QHBoxLayout(); refresh_weather, manual_weather = button("刷新天气", "secondary"), button("手动更新", "ghost")
        refresh_weather.clicked.connect(self.refresh_weather); manual_weather.clicked.connect(self.manual_weather); weather_actions.addWidget(refresh_weather); weather_actions.addWidget(manual_weather); weather_actions.addStretch(); weather_box.addLayout(weather_actions)
        lower = QGridLayout(); lower.setSpacing(16); self.layout.addLayout(lower)
        task_frame, task_box = card(); lower.addWidget(task_frame, 0, 0)
        task_head = QHBoxLayout(); task_head.addWidget(QLabel("✅  今日任务")); task_head.addStretch(); add_task = button("+ 新增", "secondary"); add_task.clicked.connect(self.add_task); self.task_progress = badge("0/6 已完成", "gray"); task_head.addWidget(add_task); task_head.addWidget(self.task_progress); task_box.addLayout(task_head)
        self.task_list = QVBoxLayout(); self.task_list.setSpacing(6); task_box.addLayout(self.task_list)
        advice_frame, advice_box = card(); lower.addWidget(advice_frame, 0, 1)
        advice_head = QHBoxLayout(); advice_head.addWidget(QLabel("✨  AI 今日建议")); advice_head.addStretch(); self.advice_source = badge("演示模式", "orange"); self.advice_generate = button("重新生成", "secondary"); self.advice_generate.clicked.connect(self.generate_advice); advice_head.addWidget(self.advice_source); advice_head.addWidget(self.advice_generate); advice_box.addLayout(advice_head)
        self.advice = QPlainTextEdit(); self.advice.setReadOnly(True); self.advice.setMinimumHeight(230); advice_box.addWidget(self.advice)
        self.layout.addStretch()
    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0); widget = item.widget()
            if widget: widget.deleteLater()
    def refresh(self):
        summary = self.window.db.finance_summary(self.window.user_id); latest = summary.get("latest", {}); trial = self.window.db.get_trial_status(self.window.user_id)
        self.revenue_card.value.setText("¥{:.0f}".format(latest.get("revenue", 0))); self.revenue_card.hint.setText("较昨日 {:+.0f} 元".format(summary.get("revenue_change", 0)))
        self.visitor_card.value.setText("{} 人".format(latest.get("visitor_count", 0))); self.visitor_card.hint.setText("优惠核销 {} 次".format(latest.get("coupon_used", 0)))
        self.profit_card.value.setText("¥{:.0f}".format(latest.get("gross_profit", 0))); self.profit_card.hint.setText("毛利率 {}%".format(latest.get("gross_margin", 0)))
        self.trial_card.value.setText("{} 天".format(trial["remaining"])); self.trial_card.hint.setText("试用已结束，仍可继续使用" if trial["expired"] else "全部功能可用")
        weather = self.window.weather_context(); tag = "、".join(weather.get("tags", [])) or "适合常规经营"; self.weather_source.setText("实时天气" if "Open-Meteo" in weather.get("source", "") else weather.get("source", "演示天气"))
        self.weather_main.setText("{} · {} · {}℃  |  {}℃ / {}℃".format(weather.get("city", "北京"), weather.get("weather", "小雨"), weather.get("temperature", 16), weather.get("high", 18), weather.get("low", 11)))
        self.weather_date.setText("日期：{}    降水概率：{}%    风速：{} km/h".format(weather.get("date", date.today().isoformat()), weather.get("precipitation_probability", 0), weather.get("wind_speed", 0)))
        impact = weather.get("business_impact") or business_impact(weather)
        self.weather_tip.setText("天气影响：{}\n经营标签：{}".format(impact, tag))
        self._clear(self.task_list); tasks = self.window.db.get_tasks(self.window.user_id); done = sum(x["status"] == "done" for x in tasks); self.task_progress.setText("{}/{} 已完成".format(done, len(tasks)))
        for task in tasks:
            line = QFrame(); l = QHBoxLayout(line); l.setContentsMargins(0, 0, 0, 0); check = QCheckBox(task["title"]); check.setChecked(task["status"] == "done"); check.toggled.connect(lambda state, item=task: self.task_changed(item, state)); l.addWidget(check, 1); action = button(task["action_label"], "ghost"); action.clicked.connect(lambda checked=False, item=task: self.window.go(item["route_name"])); remove = button("删除", "danger"); remove.clicked.connect(lambda checked=False, item=task: self.delete_task(item)); l.addWidget(action); l.addWidget(remove); self.task_list.addWidget(line)
        if not self.advice.toPlainText(): self.generate_advice()
    def task_changed(self, task, state): self.window.db.set_task_status(self.window.user_id, task["id"], "done" if state else "todo"); self.refresh()
    def add_task(self):
        dialog = TaskDialog(self.window)
        if dialog.exec_():
            try:
                values = dialog.values(); self.window.db.add_task(self.window.user_id, values["title"], values["route_name"], values["action_label"]); self.refresh()
            except ValueError as exc:
                QMessageBox.warning(self, "无法新增任务", str(exc))
    def delete_task(self, task):
        if QMessageBox.question(self, "删除任务", "确定删除“{}”吗？".format(task["title"]), QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.window.db.delete_task(self.window.user_id, task["id"]); self.refresh()
    def refresh_weather(self):
        profile = self.window.db.get_profile(self.window.user_id) or {}; self.window.run_task(lambda: WeatherService().fetch(profile.get("city", "北京")), self.weather_ready)
    def weather_ready(self, weather): self.window.save_weather(weather); self.refresh()
    def manual_weather(self):
        profile = self.window.db.get_profile(self.window.user_id) or {}; dialog = ManualWeatherDialog(profile.get("city", "北京"))
        if dialog.exec_(): self.weather_ready(dialog.value(profile.get("city", "北京")))
    def generate_advice(self):
        self.advice_generate.setEnabled(False); self.advice.setPlainText("正在根据天气、菜单、活动和近 7 日数据生成建议…")
        self.window.run_task(lambda: AIService(self.window.ai_settings()).today_advice(self.window.ai_context()), self.advice_ready, self.advice_error)
    def advice_ready(self, result):
        self.advice.setPlainText(result["content"]); self.advice_source.setText(result["source"]); self.advice_generate.setEnabled(True); self.window.db.save_generated(self.window.user_id, "今日经营建议", "Dashboard 今日建议", result["content"], result["source"])
    def advice_error(self, message): self.advice.setPlainText("生成失败：" + message); self.advice_generate.setEnabled(True)


class ContentPage(Page):
    KINDS = ("今日促销方案", "微信群文案", "朋友圈文案", "小红书标题与正文", "抖音短视频脚本", "海报文案", "评论回复话术", "私域复购话术", "会员召回话术")
    def __init__(self, window):
        super().__init__(window); self.layout.addWidget(title_block("内容生成工作台", "配置营销场景，AI 会结合店铺菜单、天气与校园节点输出可直接复制的内容。"))
        split = QSplitter(Qt.Horizontal); self.layout.addWidget(split, 1)
        left, left_box = card(); left.setMinimumWidth(315); split.addWidget(left)
        left_box.addWidget(QLabel("生成参数")); form = QFormLayout(); form.setSpacing(10)
        self.kind, self.audience, self.node, self.weather_choice, self.promote = QComboBox(), QComboBox(), QComboBox(), QComboBox(), QComboBox(); self.kind.addItems(self.KINDS)
        self.audience.addItems(("大学生", "晚自习学生", "社团活动学生", "考试周复习学生")); self.node.addItems(("自动识别", "考试周", "正常上课周", "社团招新", "运动会", "周末返校高峰")); self.weather_choice.addItems(("自动使用当前天气", "雨天", "降温", "高温", "晴天")); self.promote.addItems(("自动匹配菜单/套餐",))
        self.offer, self.style = QLineEdit("校园卡立减 2 元"), QComboBox(); self.style.addItems(("活泼年轻化", "实惠直接", "温暖关怀", "轻微紧迫感"))
        self.length = QComboBox(); self.length.addItems(("短（80 字）", "中（150 字）", "长（300 字）")); self.emoji = QCheckBox("包含适量 emoji"); self.variants = QSpinBox(); self.variants.setRange(1, 3); self.variants.setValue(1)
        for label, widget in (("内容类型", self.kind), ("目标人群", self.audience), ("校园节点", self.node), ("天气情况", self.weather_choice), ("主推商品/套餐", self.promote), ("优惠力度", self.offer), ("文案风格", self.style), ("字数", self.length), ("生成版本", self.variants)):
            form.addRow(label, widget)
        form.addRow("", self.emoji); left_box.addLayout(form); self.generate = button("✨ 生成内容"); self.generate.clicked.connect(self.generate_content); left_box.addWidget(self.generate); self.mode = QLabel("演示模式：尚未配置 API Key"); self.mode.setObjectName("muted"); self.mode.setWordWrap(True); left_box.addWidget(self.mode); left_box.addStretch()
        right, right_box = card(); split.addWidget(right); split.setStretchFactor(1, 2)
        head = QHBoxLayout(); head.addWidget(QLabel("AI 生成结果")); head.addStretch(); self.result_source = badge("等待生成", "gray"); copy = button("复制结果", "secondary"); copy.clicked.connect(lambda: copy_to_clipboard(self.result.toPlainText())); head.addWidget(self.result_source); head.addWidget(copy); right_box.addLayout(head)
        self.result = QPlainTextEdit(); self.result.setPlaceholderText("选择参数后点击“生成内容”。未配置 API 时将展示完整的 Mock 演示结果。"); right_box.addWidget(self.result, 1)
        history_card, history_box = card(); self.layout.addWidget(history_card); h = QHBoxLayout(); h.addWidget(QLabel("最近生成记录")); h.addStretch(); refresh = button("刷新", "ghost"); refresh.clicked.connect(self.refresh_history); h.addWidget(refresh); history_box.addLayout(h)
        self.history = QTableWidget(0, 4); self.history.setHorizontalHeaderLabels(("类型", "标题", "来源", "生成时间")); self.history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.history.setMaximumHeight(190); self.history.cellClicked.connect(self.load_history); history_box.addWidget(self.history)
    def refresh(self):
        profile = self.window.db.get_profile(self.window.user_id) or {}; self.promote.blockSignals(True); self.promote.clear(); self.promote.addItem("自动匹配菜单/套餐")
        for item in self.window.db.get_packages(self.window.user_id): self.promote.addItem("套餐｜{} · ¥{}".format(item["name"], item["price"]))
        for item in self.window.db.get_menu_items(self.window.user_id): self.promote.addItem("单品｜{} · ¥{}".format(item["name"], item["price"]))
        self.promote.blockSignals(False); self.mode.setText("{}：{}".format("演示模式" if not self.window.ai_settings().get("api_key") else "AI 模式", "请在设置配置 DeepSeek / OpenAI Key" if not self.window.ai_settings().get("api_key") else "将使用当前 API 配置")); self.refresh_history()
    def generate_content(self):
        parameters = {"target_audience": self.audience.currentText(), "campus_node": self.node.currentText(), "weather_choice": self.weather_choice.currentText(), "promote": self.promote.currentText(), "offer": self.offer.text().strip(), "style": self.style.currentText(), "length": self.length.currentText(), "emoji": self.emoji.isChecked(), "variants": self.variants.value()}
        self.generate.setEnabled(False); self.result.setPlainText("AI 正在组织内容，请稍候…")
        kind = self.kind.currentText(); context = self.window.ai_context(parameters)
        if self.weather_choice.currentText() != "自动使用当前天气":
            context["weather"] = dict(context["weather"], weather=self.weather_choice.currentText(), tags=[self.weather_choice.currentText()])
        self.window.run_task(lambda: AIService(self.window.ai_settings()).generate(kind, context), lambda result: self.content_ready(kind, result), self.content_error)
    def content_ready(self, kind, result):
        content = result["content"]
        if self.variants.value() > 1: content += "\n\n" + "\n\n".join("—— 版本 {} ——\n{}".format(i, content) for i in range(2, self.variants.value()+1))
        self.result.setPlainText(content); self.result_source.setText(result["source"]); self.generate.setEnabled(True); self.window.db.save_generated(self.window.user_id, kind, kind, content, result["source"])
        key = "post_group" if kind == "微信群文案" else "post_moments" if kind == "朋友圈文案" else "";
        if key: self.window.db.complete_task_key(self.window.user_id, key)
        self.refresh_history()
    def content_error(self, message): self.result.setPlainText("生成失败：" + message); self.generate.setEnabled(True)
    def refresh_history(self):
        self.records = self.window.db.generated_history(self.window.user_id); self.history.setRowCount(len(self.records))
        for row, item in enumerate(self.records):
            for col, value in enumerate((item["content_kind"], item["title"], item["source"], item["created_at"][:16].replace("T", " "))): self.history.setItem(row, col, QTableWidgetItem(str(value)))
    def load_history(self, row, _column):
        if row < len(self.records): self.result.setPlainText(self.records[row]["content"]); self.result_source.setText(self.records[row]["source"])


class DiscountRuleBuilder(QFrame):
    TYPES = ("立减", "满减", "折扣", "固定套餐价", "第二件优惠", "赠品", "限时券")
    def __init__(self, window):
        super().__init__(); self.window = window; self.setObjectName("card")
        layout = QVBoxLayout(self); layout.setContentsMargins(12, 10, 12, 10); layout.addWidget(QLabel("优惠规则构建器"))
        form = QFormLayout(); self.kind = QComboBox(); self.kind.addItems(self.TYPES); self.value = QDoubleSpinBox(); self.value.setRange(0, 99); self.value.setDecimals(1); self.value.setValue(2); self.threshold = QDoubleSpinBox(); self.threshold.setRange(0, 999); self.threshold.setDecimals(1); self.threshold.setValue(0); self.scope = QComboBox(); self.window_time = QLineEdit("17:30-22:00"); self.stackable = QCheckBox("可与其他优惠叠加"); self.gift = QLineEdit(); self.gift.setPlaceholderText("赠品名称，可选")
        for label, widget in (("优惠类型", self.kind), ("数值", self.value), ("门槛", self.threshold), ("适用商品/套餐", self.scope), ("有效时段", self.window_time), ("赠品", self.gift)): form.addRow(label, widget)
        form.addRow("", self.stackable); layout.addLayout(form); self.preview = QLabel(); self.preview.setWordWrap(True); self.preview.setObjectName("muted"); layout.addWidget(self.preview)
        for signal in (self.kind.currentTextChanged, self.value.valueChanged, self.threshold.valueChanged, self.scope.currentTextChanged, self.window_time.textChanged, self.stackable.toggled, self.gift.textChanged): signal.connect(self.update_preview)
    def refresh_options(self):
        current = self.scope.currentText(); self.scope.clear(); self.scope.addItem("全部菜单")
        for item in self.window.db.get_packages(self.window.user_id): self.scope.addItem("套餐｜{}".format(item["name"]))
        for item in self.window.db.get_menu_items(self.window.user_id): self.scope.addItem("单品｜{}".format(item["name"]))
        index = self.scope.findText(current); self.scope.setCurrentIndex(index if index >= 0 else 0); self.update_preview()
    def values(self):
        return {"type": self.kind.currentText(), "value": self.value.value(), "threshold": self.threshold.value(), "scope": self.scope.currentText(), "window": self.window_time.text().strip(), "stackable": self.stackable.isChecked(), "gift": self.gift.text().strip(), "description": self.rule_text()}
    def rule_text(self):
        kind, value, threshold = self.kind.currentText(), self.value.value(), self.threshold.value(); scope = self.scope.currentText(); time = self.window_time.text().strip() or "全天"
        if kind == "满减": text = "满 {:.0f} 元减 {:.0f} 元".format(threshold or value * 3, value)
        elif kind == "折扣": text = "{:.1f} 折".format(value or 9)
        elif kind == "固定套餐价": text = "固定套餐价 {:.0f} 元".format(value)
        elif kind == "第二件优惠": text = "第二件优惠 {:.0f} 元".format(value)
        elif kind == "赠品": text = "消费即赠 {}".format(self.gift.text().strip() or "指定小食")
        elif kind == "限时券": text = "限时券立减 {:.0f} 元".format(value)
        else: text = "立减 {:.0f} 元".format(value)
        return "{}，适用 {}，时段 {}{}".format(text, scope, time, "，可叠加" if self.stackable.isChecked() else "，不叠加")
    def update_preview(self):
        rule = self.rule_text(); risk = "风险较低，可直接执行。"
        if self.kind.currentText() in ("立减", "满减", "限时券") and self.value.value() >= 5: risk = "优惠金额偏高，建议核对套餐毛利后再发布。"
        if self.kind.currentText() == "折扣" and self.value.value() and self.value.value() < 8: risk = "折扣力度较大，建议限定时段或库存。"
        self.preview.setText("规则预览：{}\n利润提醒：{}".format(rule, risk))


class CampaignPage(Page):
    def __init__(self, window):
        super().__init__(window); self.layout.addWidget(title_block("活动策划", "围绕客流目标、套餐和校园节点，生成老板能直接执行的促销方案。"))
        split = QSplitter(Qt.Horizontal); self.layout.addWidget(split, 1)
        settings, box = card(); settings.setMinimumWidth(330); split.addWidget(settings); box.addWidget(QLabel("活动条件")); form = QFormLayout()
        self.goal, self.package, self.time = QComboBox(), QComboBox(), QComboBox(); self.goal.addItems(("提升午餐客流", "提升晚间客流", "清库存", "拉新", "复购", "考试周转化")); self.time.addItems(("AI 自动推荐", "11:30-13:30", "17:30-20:00", "19:00-22:00"))
        for label, widget in (("活动目标", self.goal), ("主推菜单/套餐", self.package), ("发布时间", self.time)): form.addRow(label, widget)
        box.addLayout(form); self.discount = DiscountRuleBuilder(window); box.addWidget(self.discount); self.plan_button = button("✨ 生成活动方案"); self.plan_button.clicked.connect(self.generate_plan); box.addWidget(self.plan_button)
        plan_hint = QLabel("提示：AI 会根据近 7 日毛利和天气给出风险提醒。"); plan_hint.setObjectName("muted"); box.addWidget(plan_hint); box.addStretch()
        result_card, result_box = card(); split.addWidget(result_card); split.setStretchFactor(1, 2); head = QHBoxLayout(); head.addWidget(QLabel("活动方案")); head.addStretch(); self.plan_source = badge("等待生成", "gray"); save = button("保存活动", "secondary"); save.clicked.connect(self.save_plan); head.addWidget(self.plan_source); head.addWidget(save); result_box.addLayout(head); self.plan = QPlainTextEdit(); self.plan.setPlaceholderText("生成后的活动名称、规则、发布时段和风险提示会显示在这里。" ); result_box.addWidget(self.plan, 1)
    def refresh(self):
        self.package.clear(); self.package.addItem("自动匹配")
        for item in self.window.db.get_packages(self.window.user_id): self.package.addItem("{} · ¥{}".format(item["name"], item["price"]))
        self.discount.refresh_options()
    def generate_plan(self):
        self.plan_button.setEnabled(False); self.last_rule = self.discount.values(); params = {"goal": self.goal.currentText(), "promote": self.package.currentText(), "offer": self.last_rule["description"], "discount_rule": self.last_rule, "publish_time": self.time.currentText()}; self.window.run_task(lambda: AIService(self.window.ai_settings()).generate("今日促销方案", self.window.ai_context(params)), self.plan_ready, self.plan_error)
    def plan_ready(self, result): self.plan.setPlainText(result["content"]); self.plan_source.setText(result["source"]); self.plan_button.setEnabled(True)
    def plan_error(self, message): self.plan.setPlainText("生成失败：" + message); self.plan_button.setEnabled(True)
    def save_plan(self):
        content = self.plan.toPlainText().strip()
        if not content: return QMessageBox.warning(self, "没有方案", "请先生成或输入活动方案。")
        name = next((line.split("：", 1)[1].strip() for line in content.splitlines() if "活动名称：" in line), "今日活动方案")
        context = self.window.ai_context(); rule = getattr(self, "last_rule", self.discount.values()); campaign_id = self.window.db.save_campaign(self.window.user_id, {"campaign_name": name, "campaign_plan": content, "node_tags": [x.get("current_node") for x in context["schools"]], "weather_snapshot": context["weather"], "publish_channels": context["profile"].get("channels", []), "publish_time": self.time.currentText(), "discount_rule": rule, "package_name": self.package.currentText(), "publish_window": rule.get("window", self.time.currentText())})
        self.window.current_campaign_id = campaign_id; self.window.current_campaign = content; self.window.db.complete_task_key(self.window.user_id, "generate_campaign"); QMessageBox.information(self, "活动已保存", "活动已保存到历史记录，并更新首页今日任务。")


class FinanceDialog(QDialog):
    def __init__(self, window, record: Optional[Dict[str, Any]] = None):
        super().__init__(window); self.window, self.record = window, record or {}; self.setWindowTitle("每日收支记录"); self.setMinimumWidth(500)
        form = QFormLayout(self); self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDate(QDate.fromString(self.record.get("record_date", date.today().isoformat()), "yyyy-MM-dd"))
        self.inputs: Dict[str, Any] = {}; fields = (("revenue", "总收入"), ("ingredient_cost", "食材成本"), ("labor_cost", "人工成本"), ("promotion_cost", "平台推广成本"), ("discount_cost", "优惠成本"), ("other_cost", "其他成本"))
        form.addRow("日期", self.day)
        for key, label in fields:
            box = QDoubleSpinBox(); box.setRange(0, 999999); box.setDecimals(2); box.setPrefix("¥ "); box.setValue(float(self.record.get(key, 0))); self.inputs[key] = box; form.addRow(label, box)
        for key, label in (("visitor_count", "到店人数"), ("coupon_used", "优惠券核销数")):
            box = QSpinBox(); box.setRange(0, 999999); box.setValue(int(self.record.get(key, 0))); self.inputs[key] = box; form.addRow(label, box)
        self.note = QPlainTextEdit(self.record.get("note", "")); self.note.setFixedHeight(70); form.addRow("备注", self.note)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def values(self):
        result = {key: widget.value() for key, widget in self.inputs.items()}; result.update({"record_date": self.day.date().toString("yyyy-MM-dd"), "note": self.note.toPlainText().strip()}); return result


class PackageMetricDialog(QDialog):
    def __init__(self, window, metric: Optional[Dict[str, Any]] = None):
        super().__init__(window); self.window, self.metric = window, metric or {}; self.setWindowTitle("记录套餐表现"); self.setMinimumWidth(470)
        form = QFormLayout(self); self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDate(QDate.fromString(self.metric.get("record_date", date.today().isoformat()), "yyyy-MM-dd")); self.package = QComboBox()
        for item in window.db.get_packages(window.user_id): self.package.addItem(item["name"], item["id"])
        index = self.package.findText(self.metric.get("package_name", "")); self.package.setCurrentIndex(index if index >= 0 else 0)
        self.orders = QSpinBox(); self.orders.setRange(0, 99999); self.orders.setValue(int(self.metric.get("order_count", 0))); self.revenue, self.cost, self.discount = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for widget, key in ((self.revenue, "revenue"), (self.cost, "ingredient_cost"), (self.discount, "discount_cost")):
            widget.setRange(0, 999999); widget.setDecimals(2); widget.setPrefix("¥ "); widget.setValue(float(self.metric.get(key, 0)))
        self.channel = QComboBox(); self.channel.addItems(("到店", "外带", "外卖", "社团团购")); self.channel.setCurrentText(self.metric.get("channel", "到店"))
        for label, widget in (("日期", self.day), ("套餐", self.package), ("订单数", self.orders), ("套餐收入", self.revenue), ("食材成本", self.cost), ("优惠成本", self.discount), ("销售场景", self.channel)): form.addRow(label, widget)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def values(self):
        return {"record_date": self.day.date().toString("yyyy-MM-dd"), "package_id": self.package.currentData(), "package_name": self.package.currentText(), "order_count": self.orders.value(), "revenue": self.revenue.value(), "ingredient_cost": self.cost.value(), "discount_cost": self.discount.value(), "channel": self.channel.currentText()}


class FinancePage(Page):
    def __init__(self, window):
        super().__init__(window); self.records: List[Dict[str, Any]] = []
        self.layout.addWidget(title_block("数据分析", "每天录入收入与成本，自动查看利润、客单价、优惠效果和 AI 经营复盘。"))
        range_row = QHBoxLayout(); range_row.addWidget(QLabel("统计范围")); self.range_mode = QComboBox(); self.range_mode.addItems(("近 7 天", "近 14 天", "近 30 天", "自定义")); self.range_start, self.range_end = QDateEdit(), QDateEdit(); self.range_start.setCalendarPopup(True); self.range_end.setCalendarPopup(True); self.range_end.setDate(QDate.currentDate()); self.range_start.setDate(QDate.currentDate().addDays(-6)); apply_range = button("应用范围", "secondary"); apply_range.clicked.connect(self.apply_range); self.range_mode.currentTextChanged.connect(self.change_range_mode); range_row.addWidget(self.range_mode); range_row.addWidget(self.range_start); range_row.addWidget(QLabel("至")); range_row.addWidget(self.range_end); range_row.addWidget(apply_range); range_row.addStretch(); self.layout.addLayout(range_row); self.change_range_mode("近 7 天")
        self.metrics = QGridLayout(); self.metrics.setSpacing(12); self.layout.addLayout(self.metrics)
        self.metric_cards = [MetricCard("当前范围收入", "--", "", "orange"), MetricCard("当前范围成本", "--", "", "blue"), MetricCard("当前范围毛利", "--", "", "green"), MetricCard("当前范围到店", "--", "", "orange")]
        for index, item in enumerate(self.metric_cards): self.metrics.addWidget(item, 0, index)
        chart_row = QGridLayout(); self.layout.addLayout(chart_row); self.money_chart = self.chart("收入 / 成本 / 毛利趋势，悬停查看数据"); self.traffic_chart = self.chart("到店人数 / 核销数趋势，悬停查看数据"); chart_row.addWidget(self.money_chart, 0, 0); chart_row.addWidget(self.traffic_chart, 0, 1)
        action_row = QHBoxLayout(); add, edit, delete = button("+ 录入今日收支"), button("编辑选中", "secondary"), button("删除选中", "danger"); add_metric, edit_metric, delete_metric = button("+ 记录套餐表现", "secondary"), button("编辑套餐表现", "ghost"), button("删除套餐表现", "danger")
        add.clicked.connect(self.add); edit.clicked.connect(self.edit); delete.clicked.connect(self.delete); add_metric.clicked.connect(self.add_package_metric); edit_metric.clicked.connect(self.edit_package_metric); delete_metric.clicked.connect(self.delete_package_metric)
        for item in (add, edit, delete, add_metric, edit_metric, delete_metric): action_row.addWidget(item)
        action_row.addStretch(); self.layout.addLayout(action_row)
        compare_split = QSplitter(Qt.Horizontal); self.layout.addWidget(compare_split); left_panel = QWidget(); left_grid = QHBoxLayout(left_panel); left_grid.setContentsMargins(0, 0, 0, 0); left_grid.setSpacing(8); self.activity_chart = self.chart("活动效果对比，到店人数"); self.package_chart = self.chart("套餐表现对比，收入与毛利贡献"); left_grid.addWidget(self.activity_chart); left_grid.addWidget(self.package_chart); compare_split.addWidget(left_panel)
        review_card, review_box = card(); compare_split.addWidget(review_card); compare_split.setStretchFactor(0, 1); compare_split.setStretchFactor(1, 1); h = QHBoxLayout(); h.addWidget(QLabel("AI 复盘建议")); h.addStretch(); self.review_source = badge("等待生成", "gray"); review = button("✨ 生成复盘", "secondary"); review.clicked.connect(self.ai_review); h.addWidget(self.review_source); h.addWidget(review); review_box.addLayout(h); self.review = QPlainTextEdit(); self.review.setReadOnly(True); self.review.setMinimumHeight(235); review_box.addWidget(self.review)
        table_card, table_box = card(); self.layout.addWidget(table_card); table_box.addWidget(QLabel("每日收支记录")); self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(("日期", "收入", "总成本", "毛利", "毛利率", "到店", "核销", "备注")); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setMinimumHeight(230); table_box.addWidget(self.table)
        package_card, package_box = card(); self.layout.addWidget(package_card); package_box.addWidget(QLabel("套餐表现明细")); self.package_table = QTableWidget(0, 7); self.package_table.setHorizontalHeaderLabels(("日期", "套餐", "订单", "收入", "食材成本", "优惠成本", "毛利贡献")); self.package_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.package_table.setSelectionBehavior(QTableWidget.SelectRows); self.package_table.setEditTriggers(QTableWidget.NoEditTriggers); self.package_table.setMinimumHeight(190); package_box.addWidget(self.package_table)
    def chart(self, title):
        frame, box = card(); box.addWidget(QLabel(title)); plot = pg.PlotWidget(); plot.setBackground("w"); plot.showGrid(x=False, y=True, alpha=0.18); plot.getAxis("left").setTextPen("#7C879D"); plot.getAxis("bottom").setTextPen("#7C879D"); plot.setMinimumHeight(230); box.addWidget(plot); frame.plot = plot; return frame
    def reset_plot(self, plot):
        plot.clear(); plot.hover_series = []
        for attr in ("hover_label", "hover_vline", "hover_hline"):
            if hasattr(plot, attr): delattr(plot, attr)
        self.ensure_hover_layer(plot)
    def ensure_hover_layer(self, plot):
        if not hasattr(plot, "hover_label"):
            plot.hover_label = pg.TextItem(anchor=(0, 1), color="#172033", fill=pg.mkBrush("#FFF7ED")); plot.hover_label.hide(); plot.addItem(plot.hover_label)
            plot.hover_vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#94A3B8", style=Qt.DashLine)); plot.hover_hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#94A3B8", style=Qt.DashLine)); plot.hover_vline.hide(); plot.hover_hline.hide(); plot.addItem(plot.hover_vline); plot.addItem(plot.hover_hline)
        if not hasattr(plot, "hover_proxy"):
            plot.hover_proxy = pg.SignalProxy(plot.scene().sigMouseMoved, rateLimit=60, slot=lambda event, target=plot: self.mouse_hover(target, event))
    def change_range_mode(self, mode):
        custom = mode == "自定义"; self.range_start.setEnabled(custom); self.range_end.setEnabled(custom)
        if not custom:
            days = int(mode.split()[1]); self.range_end.setDate(QDate.currentDate()); self.range_start.setDate(QDate.currentDate().addDays(1-days))
    def date_range(self):
        return self.range_start.date().toString("yyyy-MM-dd"), self.range_end.date().toString("yyyy-MM-dd")
    def apply_range(self): self.refresh()
    def refresh(self):
        start_date, end_date = self.date_range(); summary = self.window.db.finance_summary(self.window.user_id, start_date, end_date, days=None); self.records = summary["rows"]; self.package_records = self.window.db.list_package_metrics(self.window.user_id, start_date, end_date); self.package_totals = self.window.db.package_summary(self.window.user_id, start_date, end_date); self.campaign_records = self.window.db.list_campaigns(self.window.user_id, start_date=start_date, end_date=end_date)
        labels = (("当前范围收入", "¥{:.0f}".format(summary["revenue"]), "较上日 {:+.0f}".format(summary["revenue_change"])), ("当前范围成本", "¥{:.0f}".format(summary["total_cost"]), "食材、人工与优惠成本"), ("当前范围毛利", "¥{:.0f}".format(summary["gross_profit"]), "综合毛利率 {}%".format(summary["gross_margin"])), ("当前范围到店", "{} 人".format(summary["visitors"]), "优惠核销 {} 次".format(summary["coupons"])))
        for card_item, values in zip(self.metric_cards, labels): card_item.value.setText(values[1]); card_item.hint.setText(values[2])
        self.draw_charts(); self.table.setRowCount(len(self.records))
        for row, record in enumerate(reversed(self.records)):
            values = (record["record_date"], "¥{:.0f}".format(record["revenue"]), "¥{:.0f}".format(record["total_cost"]), "¥{:.0f}".format(record["gross_profit"]), "{}%".format(record["gross_margin"]), str(record["visitor_count"]), str(record["coupon_used"]), record["note"])
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(value))
        self.package_table.setRowCount(len(self.package_records))
        for row, record in enumerate(reversed(self.package_records)):
            values = (record["record_date"], record["package_name"], str(record["order_count"]), "¥{:.0f}".format(record["revenue"]), "¥{:.0f}".format(record["ingredient_cost"]), "¥{:.0f}".format(record["discount_cost"]), "¥{:.0f}".format(record["gross_profit"]))
            for column, value in enumerate(values): self.package_table.setItem(row, column, QTableWidgetItem(value))
    def draw_charts(self):
        rows = self.records; x = list(range(len(rows)))
        for chart in (self.money_chart, self.traffic_chart, self.activity_chart, self.package_chart):
            self.reset_plot(chart.plot)
        if not rows: return
        labels = [r["record_date"] for r in rows]
        self.add_series(self.money_chart.plot, x, [_safe_float(r["revenue"]) for r in rows], "#F97316", "收入", labels)
        self.add_series(self.money_chart.plot, x, [_safe_float(r["total_cost"]) for r in rows], "#60A5FA", "成本", labels)
        self.add_series(self.money_chart.plot, x, [_safe_float(r["gross_profit"]) for r in rows], "#22C55E", "毛利", labels)
        self.add_series(self.traffic_chart.plot, x, [_safe_int(r["visitor_count"]) for r in rows], "#F97316", "到店人数", labels)
        self.add_series(self.traffic_chart.plot, x, [_safe_int(r["coupon_used"]) for r in rows], "#8B5CF6", "优惠券核销", labels)
        campaigns = getattr(self, "campaign_records", self.window.db.list_campaigns(self.window.user_id))[:6]
        if campaigns:
            visitors = [_safe_int(item["visitor_count"]) for item in reversed(campaigns)]
            bars = pg.BarGraphItem(x=list(range(len(visitors))), height=visitors, width=0.62, brush="#FDBA74")
            self.activity_chart.plot.addItem(bars)
            self.activity_chart.plot.getAxis("bottom").setTicks([[(i, item["campaign_name"][:7]) for i, item in enumerate(reversed(campaigns))]])
        if self.package_totals:
            names = [item["package_name"] for item in self.package_totals]; revenue = [_safe_float(item["revenue"]) for item in self.package_totals]; gross = [_safe_float(item["gross_profit"]) for item in self.package_totals]
            self.package_chart.plot.addItem(pg.BarGraphItem(x=list(range(len(names))), height=revenue, width=0.62, brush="#FDBA74"))
            self.package_chart.plot.addItem(pg.BarGraphItem(x=[index + 0.32 for index in range(len(names))], height=gross, width=0.24, brush="#22C55E"))
            self.package_chart.plot.getAxis("bottom").setTicks([[(i, name[:7]) for i, name in enumerate(names)]])
            for i, (r, g) in enumerate(zip(revenue, gross)):
                rev_label = pg.TextItem("¥{:.0f}".format(r), anchor=(0.5, 0), color="#F97316"); rev_label.setPos(i, r); self.package_chart.plot.addItem(rev_label)
                gp_label = pg.TextItem("¥{:.0f}".format(g), anchor=(0.5, 0), color="#22C55E"); gp_label.setPos(i + 0.32, g); self.package_chart.plot.addItem(gp_label)
    def add_series(self, plot, x, values, color, name, labels):
        plot.plot(x, values, pen=pg.mkPen(color, width=3), name=name)
        data = [{"name": name, "date": labels[index], "value": values[index], "x": x[index], "y": values[index]} for index in range(len(values))]
        plot.hover_series.extend(data)
        scatter = pg.ScatterPlotItem(x=x, y=values, size=12, brush=color, pen=pg.mkPen("#FFFFFF", width=1), data=data, hoverable=True, hoverBrush=pg.mkBrush("#172033"))
        scatter.sigHovered.connect(lambda _item, points, _event, target=plot: self.show_hover(target, points))
        plot.addItem(scatter)
    def show_hover(self, plot, points):
        if not points: return
        data = points[0].data(); self.show_hover_data(plot, data)
    def mouse_hover(self, plot, event):
        scene_pos = event[0] if isinstance(event, tuple) else event
        if not plot.sceneBoundingRect().contains(scene_pos) or not getattr(plot, "hover_series", None):
            self.hide_hover(plot); return
        view_box = plot.plotItem.vb; nearest, distance = None, None
        for item in plot.hover_series:
            item_scene = view_box.mapViewToScene(pg.Point(float(item["x"]), float(item["y"])))
            current = (item_scene.x() - scene_pos.x()) ** 2 + (item_scene.y() - scene_pos.y()) ** 2
            if distance is None or current < distance:
                nearest, distance = item, current
        if nearest is not None and distance is not None and distance <= 28 ** 2:
            self.show_hover_data(plot, nearest)
        else:
            self.hide_hover(plot)
    def show_hover_data(self, plot, data):
        self.ensure_hover_layer(plot); x, y = float(data["x"]), float(data["y"]); value = data["value"]
        text = "{}\n{}：{}".format(data["date"], data["name"], "{:.0f}".format(value) if isinstance(value, (int, float)) else value)
        plot.hover_vline.setPos(x); plot.hover_hline.setPos(y); plot.hover_label.setText(text); plot.hover_label.setPos(x, y); plot.hover_label.show(); plot.hover_vline.show(); plot.hover_hline.show()
    def hide_hover(self, plot):
        for attr in ("hover_label", "hover_vline", "hover_hline"):
            item = getattr(plot, attr, None)
            if item: item.hide()
    def selected(self):
        row = self.table.currentRow(); return list(reversed(self.records))[row] if 0 <= row < len(self.records) else None
    def selected_package_metric(self):
        row = self.package_table.currentRow(); return list(reversed(self.package_records))[row] if 0 <= row < len(self.package_records) else None
    def add(self):
        dialog = FinanceDialog(self.window)
        if dialog.exec_(): self.window.db.save_finance(self.window.user_id, dialog.values()); self.window.db.complete_task_key(self.window.user_id, "record_finance"); self.refresh(); self.window.refresh_dashboard()
    def edit(self):
        record = self.selected()
        if not record: return QMessageBox.information(self, "请选择记录", "请先选中一条收支记录。")
        dialog = FinanceDialog(self.window, record)
        if dialog.exec_(): self.window.db.save_finance(self.window.user_id, dialog.values(), record["id"]); self.refresh(); self.window.refresh_dashboard()
    def delete(self):
        record = self.selected()
        if not record: return QMessageBox.information(self, "请选择记录", "请先选中一条收支记录。")
        if QMessageBox.question(self, "删除记录", "确定删除 {} 的收支记录吗？".format(record["record_date"]), QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes: self.window.db.delete_finance(self.window.user_id, record["id"]); self.refresh(); self.window.refresh_dashboard()
    def add_package_metric(self):
        dialog = PackageMetricDialog(self.window)
        if dialog.exec_(): self.window.db.save_package_metric(self.window.user_id, dialog.values()); self.refresh()
    def edit_package_metric(self):
        metric = self.selected_package_metric()
        if not metric: return QMessageBox.information(self, "请选择记录", "请先选中一条套餐表现。")
        dialog = PackageMetricDialog(self.window, metric)
        if dialog.exec_(): self.window.db.save_package_metric(self.window.user_id, dialog.values(), metric["id"]); self.refresh()
    def delete_package_metric(self):
        metric = self.selected_package_metric()
        if not metric: return QMessageBox.information(self, "请选择记录", "请先选中一条套餐表现。")
        if QMessageBox.question(self, "删除套餐表现", "确定删除 {} 的套餐表现吗？".format(metric["package_name"]), QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes: self.window.db.delete_package_metric(self.window.user_id, metric["id"]); self.refresh()
    def ai_review(self):
        start_date, end_date = self.date_range(); self.review.setPlainText("AI 正在复盘 {} 至 {} 的经营数据…".format(start_date, end_date)); self.window.run_task(lambda: AIService(self.window.ai_settings()).review_finance(self.window.ai_context({"date_range": "{} 至 {}".format(start_date, end_date), "package_summary": self.package_totals, "campaigns": self.window.db.list_campaigns(self.window.user_id, start_date=start_date, end_date=end_date)})), self.review_ready)
    def review_ready(self, result): self.review.setPlainText(result["content"]); self.review_source.setText(result["source"]); self.window.db.complete_task_key(self.window.user_id, "review_yesterday")


class ReplyPage(Page):
    def __init__(self, window):
        super().__init__(window); self.layout.addWidget(title_block("评论回复助手", "对好评、差评、咨询和催单生成自然得体的回复，避免推卸责任或过度承诺。"))
        frame, box = card(); self.layout.addWidget(frame); controls = QHBoxLayout(); self.kind, self.tone = QComboBox(), QComboBox(); self.kind.addItems(("好评", "差评", "咨询", "催单")); self.tone.addItems(("诚恳", "活泼", "正式")); generate, copy = button("生成回复"), button("复制", "secondary"); generate.clicked.connect(self.generate); copy.clicked.connect(lambda: copy_to_clipboard(self.result.toPlainText())); controls.addWidget(QLabel("评论类型")); controls.addWidget(self.kind); controls.addWidget(QLabel("语气")); controls.addWidget(self.tone); controls.addStretch(); controls.addWidget(generate); controls.addWidget(copy); box.addLayout(controls)
        self.comment = QPlainTextEdit(); self.comment.setPlaceholderText("粘贴顾客评价或咨询内容，例如：晚上点的关东煮等了很久，感觉有点失望。" ); self.comment.setFixedHeight(120); box.addWidget(self.comment)
        self.source = badge("等待生成", "gray"); box.addWidget(self.source); self.result = QPlainTextEdit(); self.result.setMinimumHeight(230); box.addWidget(self.result)
    def generate(self):
        if not self.comment.toPlainText().strip(): return QMessageBox.warning(self, "请输入评论", "请先粘贴顾客评论。")
        params = {"comment_type": self.kind.currentText(), "tone": self.tone.currentText(), "customer_comment": self.comment.toPlainText().strip()}; self.result.setPlainText("正在生成回复…"); self.window.run_task(lambda: AIService(self.window.ai_settings()).generate("评论回复话术", self.window.ai_context(params)), self.ready)
    def ready(self, result): self.result.setPlainText(result["content"]); self.source.setText(result["source"]); self.window.db.save_generated(self.window.user_id, "评论回复话术", "顾客评论回复", result["content"], result["source"]); self.window.db.complete_task_key(self.window.user_id, "reply_review")


class ItemDialog(QDialog):
    def __init__(self, window, title: str, fields: List[tuple], values: Optional[Dict[str, Any]] = None):
        super().__init__(window); self.setWindowTitle(title); self.fields = {}; values = values or {}; form = QFormLayout(self)
        for key, label, kind in fields:
            if kind == "price": widget = QDoubleSpinBox(); widget.setRange(0, 99999); widget.setDecimals(2); widget.setValue(float(values.get(key, 0)))
            else: widget = QLineEdit(str(values.get(key, "")))
            self.fields[key] = widget; form.addRow(label, widget)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def values(self): return {key: widget.value() if isinstance(widget, QDoubleSpinBox) else widget.text().strip() for key, widget in self.fields.items()}


class SchoolScheduleDialog(QDialog):
    def __init__(self, window, school: Dict[str, Any]):
        super().__init__(window); self.setWindowTitle("管理 {} 的校园时段".format(school["name"])); self.setMinimumWidth(520)
        form = QFormLayout(self); self.node = QComboBox(); self.node.addItems(("正常上课周", "考试周", "开学季", "毕业季", "社团招新", "运动会", "放假前一周", "周末返校高峰")); self.node.setCurrentText(school.get("current_node", "正常上课周"))
        self.detail = QLineEdit(school.get("node_detail", "")); self.class_times = QLineEdit(school.get("class_time_slots", "")); self.lunch = QLineEdit(school.get("lunch_peak_slots", "")); self.evening = QLineEdit(school.get("evening_peak_slots", "")); self.tip = QPlainTextEdit(school.get("operating_tip", "")); self.tip.setFixedHeight(70)
        for label, widget in (("节点状态", self.node), ("节点说明", self.detail), ("典型上下课时间", self.class_times), ("午餐高峰", self.lunch), ("晚餐/晚自习高峰", self.evening), ("经营建议", self.tip)): form.addRow(label, widget)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); form.addRow(actions)
    def values(self):
        return {"current_node": self.node.currentText(), "node_detail": self.detail.text().strip(), "class_time_slots": self.class_times.text().strip(), "lunch_peak_slots": self.lunch.text().strip(), "evening_peak_slots": self.evening.text().strip(), "operating_tip": self.tip.toPlainText().strip()}


class SettingsPage(Page):
    def __init__(self, window):
        super().__init__(window); self.layout.addWidget(title_block("设置", "维护店铺、菜单、学校节点与 AI 配置。所有数据仅保存到本机。"))
        self.tabs = QTabWidget(); self.layout.addWidget(self.tabs, 1); self.profile_tab = self.build_profile(); self.menu_tab = self.build_menu(); self.api_tab = self.build_api(); self.campus_tab = self.build_campus(); self.tabs.addTab(self.profile_tab, "店铺信息"); self.tabs.addTab(self.menu_tab, "菜单与套餐"); self.tabs.addTab(self.campus_tab, "学校与天气"); self.tabs.addTab(self.api_tab, "AI API 配置")
    def build_profile(self):
        page = QWidget(); layout = QVBoxLayout(page); frame, box = card(); layout.addWidget(frame); self.editor = ProfileEditor(self.window.db.get_profile(self.window.user_id)); box.addWidget(QLabel("店铺基础信息")); box.addWidget(self.editor); save = button("保存并更新附近学校"); save.clicked.connect(self.save_profile); box.addWidget(save); reset = button("重置为东门小吃铺 Demo 数据", "danger"); reset.clicked.connect(self.reset_demo); box.addWidget(reset); layout.addStretch(); return page
    def build_menu(self):
        page = QWidget(); layout = QVBoxLayout(page); tabs = QTabWidget(); layout.addWidget(tabs)
        menu_page = QWidget(); m = QVBoxLayout(menu_page); actions = QHBoxLayout(); add = button("+ 新增单品"); add.clicked.connect(self.add_menu); actions.addWidget(add); actions.addStretch(); m.addLayout(actions); self.menu_table = QTableWidget(0, 3); self.menu_table.setHorizontalHeaderLabels(("单品", "类别", "价格")); self.menu_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); m.addWidget(self.menu_table); tabs.addTab(menu_page, "单品菜单")
        package_page = QWidget(); p = QVBoxLayout(package_page); add_pack = button("+ 新增套餐"); add_pack.clicked.connect(self.add_package); p.addWidget(add_pack); self.package_table = QTableWidget(0, 4); self.package_table.setHorizontalHeaderLabels(("套餐", "组合", "价格", "适用场景")); self.package_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); p.addWidget(self.package_table); tabs.addTab(package_page, "套餐")
        return page
    def build_campus(self):
        page = QWidget(); layout = QVBoxLayout(page); frame, box = card(); layout.addWidget(frame); box.addWidget(QLabel("附近学校与校园运营时段"))
        school_actions = QHBoxLayout(); school_actions.addWidget(QLabel("选中学校后可维护上下课、用餐高峰和经营建议。")); school_actions.addStretch(); edit_school = button("编辑选中学校", "secondary"); edit_school.clicked.connect(self.edit_school); school_actions.addWidget(edit_school); box.addLayout(school_actions)
        self.school_table = QTableWidget(0, 7); self.school_table.setHorizontalHeaderLabels(("学校", "距离", "当前节点", "上下课", "午餐高峰", "晚间高峰", "经营提示")); self.school_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.school_table.setMaximumHeight(230); self.school_table.setSelectionBehavior(QTableWidget.SelectRows); self.school_table.setEditTriggers(QTableWidget.NoEditTriggers); box.addWidget(self.school_table)
        box.addWidget(QLabel("手动添加校园事件")); line = QHBoxLayout(); self.event_school = QComboBox(); self.event_title = QLineEdit(); self.event_title.setPlaceholderText("例如：运动会、放假前一周、社团招新"); self.event_start, self.event_end = QDateEdit(), QDateEdit(); self.event_start.setCalendarPopup(True); self.event_end.setCalendarPopup(True); self.event_start.setDate(QDate.currentDate()); self.event_end.setDate(QDate.currentDate().addDays(7)); add = button("添加事件", "secondary"); add.clicked.connect(self.add_event); line.addWidget(self.event_school); line.addWidget(self.event_title, 1); line.addWidget(self.event_start); line.addWidget(self.event_end); line.addWidget(add); box.addLayout(line); self.event_list = QLabel(); self.event_list.setWordWrap(True); self.event_list.setObjectName("muted"); box.addWidget(self.event_list)
        weather_frame, weather_box = card(); layout.addWidget(weather_frame); weather_box.addWidget(QLabel("天气服务配置（已预留真实 API 接入）")); weather_form = QFormLayout(); self.weather_provider = QComboBox(); self.weather_provider.addItems(("Open-Meteo（默认，无需 Key）", "自定义天气 API（预留）")); self.weather_api_url = QLineEdit(self.window.db.get_setting(self.window.user_id, "weather_api_url", "")); self.weather_api_url.setPlaceholderText("可选：未来接入天气服务的 Base URL"); weather_form.addRow("服务", self.weather_provider); weather_form.addRow("自定义 Base URL", self.weather_api_url); weather_box.addLayout(weather_form); save_weather = button("保存天气设置", "secondary"); save_weather.clicked.connect(self.save_weather_settings); weather_box.addWidget(save_weather); layout.addStretch(); return page
    def build_api(self):
        page = QWidget(); layout = QVBoxLayout(page); frame, box = card(); layout.addWidget(frame); box.addWidget(QLabel("AI API 配置")); form = QFormLayout(); current = self.window.ai_settings(); self.provider = QComboBox(); self.provider.addItems(("DeepSeek", "OpenAI", "其他兼容 OpenAI 格式")); self.provider.setCurrentText(self.window.db.get_setting(self.window.user_id, "ai_provider", "DeepSeek")); self.base_url = QLineEdit(current.get("base_url", "https://api.deepseek.com")); self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.Password); self.api_key.setPlaceholderText("已保存" if current.get("api_key") else "输入 API Key"); self.model = QLineEdit(current.get("model", "deepseek-chat")); self.temperature = QDoubleSpinBox(); self.temperature.setRange(0, 2); self.temperature.setSingleStep(.1); self.temperature.setValue(float(current.get("temperature", .7))); self.max_tokens = QSpinBox(); self.max_tokens.setRange(100, 16000); self.max_tokens.setValue(int(current.get("max_tokens", 2000))); self.stream = QCheckBox("启用流式响应"); self.stream.setChecked(bool(current.get("stream", False)))
        for label, widget in (("Provider", self.provider), ("Base URL", self.base_url), ("API Key", self.api_key), ("Model Name", self.model), ("Temperature", self.temperature), ("Max Tokens", self.max_tokens)): form.addRow(label, widget)
        form.addRow("", self.stream); box.addLayout(form); actions = QHBoxLayout(); save, test = button("保存配置"), button("测试连接", "secondary"); save.clicked.connect(self.save_api); test.clicked.connect(self.test_api); actions.addWidget(save); actions.addWidget(test); box.addLayout(actions)
        self.api_status = QLabel("未配置 Key 时，系统会使用完整 Mock AI，适合现场 Demo。"); self.api_status.setObjectName("muted"); self.api_status.setWordWrap(True); box.addWidget(self.api_status); layout.addStretch(); self.provider.currentTextChanged.connect(self.provider_changed); return page
    def refresh(self):
        profile = self.window.db.get_profile(self.window.user_id) or {}; self.editor = self._replace_profile_editor(self.editor, profile); self.refresh_menu(); self.refresh_schools()
    def _replace_profile_editor(self, old, profile):
        parent_layout = old.parentWidget().layout(); index = parent_layout.indexOf(old); old.setParent(None); editor = ProfileEditor(profile); parent_layout.insertWidget(index, editor); return editor
    def save_profile(self):
        try: self.window.db.save_profile(self.window.user_id, self.editor.values()); self.window.refresh_all(); QMessageBox.information(self, "已保存", "店铺资料和附近学校已更新。")
        except ValueError as exc: QMessageBox.warning(self, "请补充信息", str(exc))
    def reset_demo(self):
        if QMessageBox.question(self, "恢复 Demo", "这会重置当前账号的菜单、活动、任务和收支演示数据，确定继续吗？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes: self.window.db.reset_demo_data(self.window.user_id, mark_seeded=True); self.window.refresh_all(); QMessageBox.information(self, "已恢复", "东门小吃铺 V2 Demo 数据已恢复。")
    def refresh_menu(self):
        menu = self.window.db.get_menu_items(self.window.user_id); self.menu_table.setRowCount(len(menu))
        for row, item in enumerate(menu):
            for col, value in enumerate((item["name"], item["category"], "¥{}".format(item["price"]))): self.menu_table.setItem(row, col, QTableWidgetItem(str(value)))
        packages = self.window.db.get_packages(self.window.user_id); self.package_table.setRowCount(len(packages))
        for row, item in enumerate(packages):
            for col, value in enumerate((item["name"], item["items"], "¥{}".format(item["price"]), item["target_scene"])): self.package_table.setItem(row, col, QTableWidgetItem(str(value)))
    def add_menu(self):
        dialog = ItemDialog(self.window, "新增单品", [("name", "名称", "text"), ("category", "类别", "text"), ("price", "价格", "price")])
        if dialog.exec_(): self.window.db.save_menu_item(self.window.user_id, dialog.values()); self.refresh_menu()
    def add_package(self):
        dialog = ItemDialog(self.window, "新增套餐", [("name", "套餐名称", "text"), ("items", "套餐组合", "text"), ("price", "价格", "price"), ("target_scene", "适用场景", "text")])
        if dialog.exec_(): self.window.db.save_package(self.window.user_id, dialog.values()); self.refresh_menu()
    def refresh_schools(self):
        self.schools = self.window.db.get_schools(self.window.user_id); self.school_table.setRowCount(len(self.schools)); self.event_school.clear(); self.event_school.addItem("全店通用事件", None)
        schools = self.schools
        for row, item in enumerate(schools):
            self.event_school.addItem(item["name"], item["id"])
            for col, value in enumerate((item["name"], "{}m".format(item["distance_m"]), item["current_node"], item.get("class_time_slots", ""), item.get("lunch_peak_slots", ""), item.get("evening_peak_slots", ""), item.get("operating_tip", item["node_detail"]))): self.school_table.setItem(row, col, QTableWidgetItem(str(value)))
        events = self.window.db.campus_events(self.window.user_id); self.event_list.setText("当前事件：" + "；".join("{} · {}".format(item.get("school_name") or "全店", item["title"]) for item in events))
    def edit_school(self):
        row = self.school_table.currentRow()
        if row < 0 or row >= len(getattr(self, "schools", [])):
            return QMessageBox.information(self, "请选择学校", "请先选中一所学校。")
        school = self.schools[row]; dialog = SchoolScheduleDialog(self.window, school)
        if dialog.exec_():
            self.window.db.update_school(self.window.user_id, school["id"], dialog.values()); self.refresh_schools(); self.window.refresh_dashboard()
    def add_event(self):
        title = self.event_title.text().strip()
        if not title: return
        self.window.db.add_campus_event(self.window.user_id, {"title": title, "school_id": self.event_school.currentData(), "start_date": self.event_start.date().toString("yyyy-MM-dd"), "end_date": self.event_end.date().toString("yyyy-MM-dd")}); self.event_title.clear(); self.refresh_schools(); self.window.refresh_dashboard()
    def save_weather_settings(self):
        self.window.db.set_setting(self.window.user_id, "weather_provider", self.weather_provider.currentText())
        self.window.db.set_setting(self.window.user_id, "weather_api_url", self.weather_api_url.text().strip())
        QMessageBox.information(self, "已保存", "天气设置已保存；当前仍可在 Dashboard 手动更新或使用 Open-Meteo。")
    def provider_changed(self, provider):
        if provider == "DeepSeek": self.base_url.setText("https://api.deepseek.com"); self.model.setText("deepseek-chat")
        elif provider == "OpenAI": self.base_url.setText("https://api.openai.com/v1"); self.model.setText("gpt-4o-mini")
    def api_values(self):
        old = self.window.ai_settings(); return {"provider": self.provider.currentText(), "base_url": self.base_url.text().strip(), "api_key": self.api_key.text().strip() or old.get("api_key", ""), "model": self.model.text().strip(), "temperature": self.temperature.value(), "max_tokens": self.max_tokens.value(), "stream": self.stream.isChecked()}
    def save_api(self):
        values = self.api_values()
        for key, value in (("ai_provider", values["provider"]), ("ai_base_url", values["base_url"]), ("ai_model", values["model"]), ("ai_temperature", str(values["temperature"])), ("ai_max_tokens", str(values["max_tokens"])), ("ai_stream", "1" if values["stream"] else "0")): self.window.db.set_setting(self.window.user_id, key, value)
        if self.api_key.text().strip(): self.window.db.set_setting(self.window.user_id, "ai_api_key", self.api_key.text().strip(), secret=True)
        self.api_key.clear(); self.api_status.setText("已保存。API Key 已加密保存且不会在界面回显。")
    def test_api(self):
        values = self.api_values(); self.api_status.setText("正在测试连接…")
        self.window.run_task(lambda: AIClient(values).test_connection(), lambda result: self.api_status.setText("连接成功：" + result), lambda message: self.api_status.setText("连接失败：" + message))


class MainWindow(QMainWindow):
    def __init__(self, db: V2Database, user: Dict[str, Any]):
        super().__init__(); self.db, self.user_id, self.username, self._threads = db, user["id"], user["username"], []; self.current_campaign = ""; self.current_campaign_id = None
        self.setWindowTitle(APP_NAME + " · V2"); self.resize(1440, 900); self.setMinimumSize(1180, 760)
        root = QWidget(); self.setCentralWidget(root); shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(218); side_box = QVBoxLayout(side); side_box.setContentsMargins(18, 25, 18, 18); side_box.setSpacing(8); shell.addWidget(side)
        brand = QLabel("🍢 东门增长台"); brand.setObjectName("brand"); side_box.addWidget(brand); sub = QLabel("校园商家 AI Copilot"); sub.setObjectName("brandSub"); side_box.addWidget(sub); side_box.addSpacing(22)
        self.nav = QListWidget(); self.nav.setObjectName("navigation"); self.pages_order = ("Dashboard", "内容生成", "活动策划", "数据分析", "评论回复", "设置"); self.nav.addItems(("▦  Dashboard", "✦  内容生成", "◈  活动策划", "▥  数据分析", "☻  评论回复", "⚙  设置")); side_box.addWidget(self.nav, 1)
        local_label = QLabel("V2 Demo · 本地数据"); local_label.setObjectName("brandSub"); side_box.addWidget(local_label); logout = button("退出登录", "ghost"); logout.clicked.connect(self.logout); side_box.addWidget(logout)
        content = QWidget(); content.setObjectName("contentArea"); content_box = QVBoxLayout(content); content_box.setContentsMargins(0, 0, 0, 0); content_box.setSpacing(0); shell.addWidget(content, 1)
        header = QFrame(); header.setStyleSheet("QFrame { background:white; border-bottom:1px solid #EDF0F5; }"); head = QHBoxLayout(header); head.setContentsMargins(28, 13, 28, 13); self.header_title = QLabel("Dashboard"); self.header_title.setStyleSheet("font-size:16px;font-weight:800;color:#172033;"); head.addWidget(self.header_title); head.addStretch(); self.ai_mode = badge("AI 演示模式", "orange"); self.trial_badge = badge("试用剩余 -- 天", "green"); head.addWidget(self.ai_mode); head.addWidget(self.trial_badge); content_box.addWidget(header)
        self.stack = QStackedWidget(); content_box.addWidget(self.stack, 1); self.pages = {"Dashboard": DashboardPage(self), "内容生成": ContentPage(self), "活动策划": CampaignPage(self), "数据分析": FinancePage(self), "评论回复": ReplyPage(self), "设置": SettingsPage(self)}
        for name in self.pages_order: self.stack.addWidget(self.pages[name])
        self.nav.currentRowChanged.connect(self.changed); self.nav.setCurrentRow(0)
    def run_task(self, fn, success, failure=None):
        thread, worker = QThread(self), Worker(fn); worker.moveToThread(thread); thread.started.connect(worker.run); worker.done.connect(success); worker.failed.connect(failure or self.show_error); worker.done.connect(thread.quit); worker.failed.connect(thread.quit); thread.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater); thread.finished.connect(lambda: self._threads.remove((thread, worker)) if (thread, worker) in self._threads else None); self._threads.append((thread, worker)); thread.start()
    def show_error(self, message): QMessageBox.warning(self, "操作失败", message)
    def changed(self, index):
        if index < 0: return
        name = self.pages_order[index]; self.header_title.setText(name); self.stack.setCurrentIndex(index); self.pages[name].refresh(); self.update_header()
    def go(self, name): self.nav.setCurrentRow(self.pages_order.index(name))
    def ai_settings(self):
        settings = self.db.get_ai_settings(self.user_id); provider = self.db.get_setting(self.user_id, "ai_provider", "DeepSeek")
        if provider == "DeepSeek" and not self.db.get_setting(self.user_id, "ai_base_url", ""): settings.update({"base_url": "https://api.deepseek.com", "model": "deepseek-chat"})
        return settings
    def weather_context(self):
        raw = self.db.get_setting(self.user_id, "weather_cache", "")
        if raw:
            try: return json.loads(raw)
            except json.JSONDecodeError: pass
        weather = {"city": "北京", "date": date.today().isoformat(), "weather": "小雨", "temperature": 16, "high": 18, "low": 11, "precipitation_probability": 75, "wind_speed": 6, "tags": ["雨天", "降温"], "source": "V2 演示天气"}
        weather["business_impact"] = business_impact(weather)
        return weather
    def save_weather(self, weather): self.db.set_setting(self.user_id, "weather_cache", json.dumps(weather, ensure_ascii=False))
    def ai_context(self, parameters: Optional[Dict[str, Any]] = None):
        params = parameters or {}; summary = self.db.finance_summary(self.user_id); package_metrics = self.db.package_summary(self.user_id)
        if params.get("date_range"):
            dates = params["date_range"].split(" 至 ")
            if len(dates) == 2:
                summary = self.db.finance_summary(self.user_id, dates[0], dates[1], days=None); package_metrics = self.db.package_summary(self.user_id, dates[0], dates[1])
        return {"profile": self.db.get_profile(self.user_id) or {}, "menu": self.db.get_menu_items(self.user_id), "packages": self.db.get_packages(self.user_id), "schools": self.db.get_schools(self.user_id), "events": self.db.campus_events(self.user_id), "weather": self.weather_context(), "finance": {"revenue": summary["revenue"], "gross_margin": summary["gross_margin"], "rows": summary["rows"]}, "package_metrics": package_metrics, "campaigns": self.db.list_campaigns(self.user_id, days=30), "parameters": params}
    def refresh_dashboard(self): self.pages["Dashboard"].refresh(); self.update_header()
    def refresh_all(self):
        for page in self.pages.values(): page.refresh()
        self.update_header()
    def update_header(self):
        trial = self.db.get_trial_status(self.user_id); self.trial_badge.setText("试用已结束" if trial["expired"] else "试用剩余 {} 天".format(trial["remaining"])); self.ai_mode.setText("AI 演示模式" if not self.ai_settings().get("api_key") else "AI 已连接")
    def logout(self): self.db.clear_session(); QMessageBox.information(self, "已退出", "已清除本地登录状态，重新打开软件可登录其他账号。"); self.close()


def main():
    app = QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setFont(QFont("Microsoft YaHei UI", 10)); app.setStyleSheet(STYLE); pg.setConfigOptions(antialias=True)
    db = V2Database(); session_user = db.restore_session(); user = db.get_user(session_user) if session_user else None
    if not user:
        login = LoginDialog(db)
        if not login.exec_(): return 0
        user = login.user
    window = MainWindow(db, user)
    if not db.get_profile(user["id"]):
        onboarding = OnboardingDialog(window)
        if not onboarding.exec_(): return 0
    window.refresh_all(); window.show(); return app.exec_()


if __name__ == "__main__": sys.exit(main())
