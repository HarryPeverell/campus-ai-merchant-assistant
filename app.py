"""校圈小店 AI 增长助理桌面入口。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QScrollArea, QSpinBox, QDoubleSpinBox,
    QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from campus_growth import APP_NAME
from campus_growth.core import Database
from campus_growth.services.ai_request import complete
from campus_growth.services.calendar_analysis import analyze_calendar
from campus_growth.services.calendar_service import CalendarImportError, extract_file, extract_url
from campus_growth.services.client import AIClient
from campus_growth.services.generator import campus_nodes, generate_campaign, generate_content, generate_reply
from campus_growth.services.weather import WeatherService


STYLE = """
QMainWindow, QDialog { background: #f6f8fb; color: #1f2937; }
QLabel#title { font-size: 24px; font-weight: 700; color: #14213d; }
QLabel#subtle { color: #64748b; }
QPushButton { background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #1d4ed8; }
QPushButton[secondary="true"] { background: #e2e8f0; color: #1e293b; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #cbd5e1; border-radius: 5px; padding: 6px; }
QGroupBox { background: white; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 12px; padding: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QListWidget { background: #14213d; color: #e2e8f0; border: 0; padding: 8px; }
QListWidget::item { padding: 11px; border-radius: 5px; } QListWidget::item:selected { background: #2563eb; }
QTableWidget { background: white; border: 1px solid #e2e8f0; gridline-color: #e2e8f0; }
"""


def secondary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("secondary", True)
    return button


def card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    return group, layout


def copy_text(text: str) -> None:
    QApplication.clipboard().setText(text)


class TaskWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn

    @pyqtSlot()
    def run(self):
        try:
            self.finished.emit(self.fn())
        except Exception as exc:  # 所有外部服务均在此转为用户可见错误
            self.failed.emit(str(exc))


class LoginDialog(QDialog):
    def __init__(self, db: Database):
        super().__init__()
        self.db, self.user = db, None
        self.setWindowTitle(APP_NAME + " - 登录")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        title = QLabel(APP_NAME); title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(QLabel("本地 MVP 演示账号：admin / admin"))
        form = QFormLayout()
        self.username, self.password = QLineEdit("admin"), QLineEdit("admin")
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("账号", self.username); form.addRow("密码", self.password)
        layout.addLayout(form)
        self.remember = QCheckBox("7 天内保持登录"); self.remember.setChecked(True)
        layout.addWidget(self.remember)
        buttons = QHBoxLayout()
        login, register = QPushButton("登录"), secondary("注册本地账号")
        login.clicked.connect(self.login); register.clicked.connect(self.register)
        buttons.addWidget(login); buttons.addWidget(register); layout.addLayout(buttons)

    def login(self):
        user = self.db.authenticate(self.username.text(), self.password.text())
        if not user:
            QMessageBox.warning(self, "登录失败", "账号或密码错误。")
            return
        self.user = user
        if self.remember.isChecked():
            self.db.save_session(user["id"])
        else:
            self.db.clear_session()
        self.accept()

    def register(self):
        try:
            self.db.create_user(self.username.text(), self.password.text())
            QMessageBox.information(self, "注册成功", "本地账号已创建，请点击登录。")
        except ValueError as exc:
            QMessageBox.warning(self, "无法注册", str(exc))


class ProfileForm(QWidget):
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__()
        profile = profile or {}
        form = QFormLayout(self)
        self.fields: Dict[str, QLineEdit] = {}
        definitions = [
            ("store_name", "店铺名称 *"), ("business_type", "主营业务 *"), ("products", "主要商品/服务 *"),
            ("price_range", "价格范围 *"), ("city", "所在城市 *"), ("address", "店铺地址"),
            ("school_name", "附近学校 *"), ("target_students", "目标学生（逗号分隔）"),
            ("discount_options", "可接受优惠（逗号分隔）"), ("business_hours", "营业时间"),
            ("channels", "发布渠道（逗号分隔）"),
        ]
        for key, label in definitions:
            raw = profile.get(key, "")
            value = "，".join(raw) if isinstance(raw, list) else str(raw or "")
            field = QLineEdit(value); self.fields[key] = field; form.addRow(label, field)

    def value(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        for key, field in self.fields.items():
            raw = field.text().strip()
            if key in {"target_students", "discount_options", "channels"}:
                output[key] = [x.strip() for x in raw.replace("、", "，").replace(",", "，").split("，") if x.strip()]
            else:
                output[key] = raw
        return output

    def load_profile(self, profile: Dict[str, Any]) -> None:
        for key, field in self.fields.items():
            raw = profile.get(key, "")
            field.setText("，".join(raw) if isinstance(raw, list) else str(raw or ""))


class ProfileDialog(QDialog):
    def __init__(self, main, first_run: bool = False):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("首次配置店铺信息" if first_run else "编辑店铺信息")
        self.setMinimumSize(560, 460)
        layout = QVBoxLayout(self)
        hint = QLabel("带 * 的字段用于活动和文案生成，首次使用必须完成。")
        hint.setObjectName("subtle"); layout.addWidget(hint)
        self.form = ProfileForm(main.db.get_profile(main.user_id)); layout.addWidget(self.form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def save(self):
        try:
            self.main.db.save_profile(self.main.user_id, self.form.value())
            self.main.refresh_all(); self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "无法保存", str(exc))


class ManualWeatherDialog(QDialog):
    def __init__(self, city: str):
        super().__init__()
        self.setWindowTitle("手动输入天气")
        form = QFormLayout(self)
        self.weather = QLineEdit("小雨")
        self.temperature, self.high, self.low, self.precip = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for box, value in ((self.temperature, 22), (self.high, 25), (self.low, 19), (self.precip, 70)):
            box.setRange(-50, 100); box.setValue(value)
        form.addRow("城市", QLabel(city)); form.addRow("天气", self.weather); form.addRow("当前温度 ℃", self.temperature)
        form.addRow("最高温 ℃", self.high); form.addRow("最低温 ℃", self.low); form.addRow("降水概率 %", self.precip)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def value(self, city: str) -> Dict[str, Any]:
        return WeatherService.manual(city, self.weather.text(), self.temperature.value(), self.high.value(), self.low.value(), self.precip.value())


class HomePage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main
        layout = QVBoxLayout(self)
        self.title = QLabel(); self.title.setObjectName("title"); layout.addWidget(self.title)
        self.trial = QLabel(); self.trial.setObjectName("subtle"); layout.addWidget(self.trial)
        grid = QGridLayout(); layout.addLayout(grid)
        self.weather_label = QLabel(); self.weather_label.setWordWrap(True)
        self.node_label = QLabel(); self.node_label.setWordWrap(True)
        self.advice_label = QLabel(); self.advice_label.setWordWrap(True)
        for column, (name, label) in enumerate((("今日天气", self.weather_label), ("校园节点", self.node_label), ("今日建议", self.advice_label))):
            group, box = card(name); box.addWidget(label); grid.addWidget(group, 0, column)
        buttons = QHBoxLayout()
        refresh, manual, campaign, content = QPushButton("刷新天气"), secondary("手动天气"), QPushButton("生成今日活动"), secondary("生成宣传文案")
        refresh.clicked.connect(self.refresh_weather); manual.clicked.connect(self.manual_weather)
        campaign.clicked.connect(lambda: self.main.go("今日活动")); content.clicked.connect(lambda: self.main.go("内容生成"))
        for button in (refresh, manual, campaign, content): buttons.addWidget(button)
        layout.addLayout(buttons); layout.addStretch()

    def refresh(self):
        profile = self.main.db.get_profile(self.main.user_id) or {}
        trial = self.main.db.get_trial_status(self.main.user_id)
        self.title.setText(profile.get("store_name", "请先配置店铺信息") + " · 今日经营工作台")
        self.trial.setText("试用已结束，功能仍可继续使用。" if trial["expired"] else "免费试用剩余 {} 天".format(trial["remaining"]))
        weather, calendar, tags, slot = self.main.context()
        self.weather_label.setText("{} · {}\n当前 {}℃，最高/最低 {}℃ / {}℃\n降水概率 {}%\n来源：{}".format(weather.get("city"), weather.get("weather"), weather.get("temperature"), weather.get("high"), weather.get("low"), weather.get("precipitation_probability"), weather.get("source")))
        self.node_label.setText("标签：{}\n校历：{}".format("、".join(tags) or "暂未识别", calendar.get("parsed_summary", "尚未配置校历")[:180]))
        self.advice_label.setText("推荐经营时段：{}\n优先结合 {} 设计活动，并发布到 {}。".format(slot, "、".join(tags) or "上下课时段", "、".join(profile.get("channels", [])) or "微信群、朋友圈"))

    def refresh_weather(self):
        profile = self.main.db.get_profile(self.main.user_id)
        if not profile:
            QMessageBox.warning(self, "请先配置", "请先完成店铺信息配置。")
            return
        self.main.run_task(lambda: WeatherService().fetch(profile["city"]), self.weather_ready)

    def weather_ready(self, weather):
        self.main.db.set_setting(self.main.user_id, "weather_cache", json.dumps(weather, ensure_ascii=False))
        self.refresh()

    def manual_weather(self):
        profile = self.main.db.get_profile(self.main.user_id) or {}
        dialog = ManualWeatherDialog(profile.get("city", ""))
        if dialog.exec_():
            weather = dialog.value(profile.get("city", ""))
            self.weather_ready(weather)


class CampaignPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main
        layout = QVBoxLayout(self)
        title = QLabel("今日活动"); title.setObjectName("title"); layout.addWidget(title)
        form = QHBoxLayout(); self.objective, self.offer = QLineEdit("提升到店量"), QLineEdit()
        self.objective.setPlaceholderText("活动目标"); self.offer.setPlaceholderText("指定优惠力度（可选）")
        form.addWidget(self.objective); form.addWidget(self.offer); layout.addLayout(form)
        actions = QHBoxLayout(); self.generate = QPushButton("生成今日活动"); self.save = secondary("保存活动方案")
        self.generate.clicked.connect(self.generate_campaign); self.save.clicked.connect(self.save_campaign)
        actions.addWidget(self.generate); actions.addWidget(self.save); layout.addLayout(actions)
        self.source = QLabel(); self.source.setObjectName("subtle"); layout.addWidget(self.source)
        self.output = QPlainTextEdit(); self.output.setPlaceholderText("活动方案会显示在这里，可直接编辑。")
        layout.addWidget(self.output, 1)

    def generate_campaign(self):
        profile, weather, calendar, tags, slot = self.main.context(full=True)
        if not profile:
            QMessageBox.warning(self, "请先配置", "请先完成店铺信息配置。")
            return
        self.generate.setEnabled(False); self.source.setText("正在生成…")
        settings = self.main.db.get_ai_settings(self.main.user_id)
        self.main.run_task(lambda: generate_campaign(profile, weather, calendar, tags, slot, settings, self.objective.text(), self.offer.text()), self.generated, lambda message: self.failed(message))

    def generated(self, result):
        text, source = result; self.output.setPlainText(text); self.source.setText("来源：" + source)
        self.main.current_campaign = text; self.generate.setEnabled(True)

    def failed(self, message):
        self.generate.setEnabled(True); self.source.setText("生成失败：" + message)

    def save_campaign(self):
        text = self.output.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "没有内容", "请先生成或输入活动方案。")
            return
        name = next((x.split("：", 1)[1] for x in text.splitlines() if x.startswith("活动名称：")), "未命名活动")
        profile, weather, _calendar, tags, _slot = self.main.context(full=True)
        self.main.current_campaign_id = self.main.db.save_campaign(self.main.user_id, {"campaign_name": name.strip(), "campaign_plan": text, "node_tags": tags, "weather_snapshot": weather, "publish_channels": profile.get("channels", [])})
        self.main.current_campaign = text
        QMessageBox.information(self, "已保存", "活动方案已保存，可在数据复盘页补充效果数据。")

    def refresh(self):
        if self.main.current_campaign and not self.output.toPlainText(): self.output.setPlainText(self.main.current_campaign)


class ContentPage(QWidget):
    CHANNELS = ("微信群", "朋友圈", "小红书", "抖音", "海报")
    def __init__(self, main):
        super().__init__(); self.main = main; self.outputs: Dict[str, QPlainTextEdit] = {}
        layout = QVBoxLayout(self); title = QLabel("内容一键生成"); title.setObjectName("title"); layout.addWidget(title)
        controls = QHBoxLayout(); self.channel = QComboBox(); self.channel.addItems(self.CHANNELS)
        one, all_button, copy = QPushButton("生成当前渠道"), QPushButton("生成全部渠道"), secondary("复制当前内容")
        one.clicked.connect(self.generate_one); all_button.clicked.connect(self.generate_all); copy.clicked.connect(self.copy_current)
        controls.addWidget(self.channel); controls.addWidget(one); controls.addWidget(all_button); controls.addWidget(copy); layout.addLayout(controls)
        self.source = QLabel(); self.source.setObjectName("subtle"); layout.addWidget(self.source)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)
        for channel in self.CHANNELS:
            box = QPlainTextEdit(); box.setPlaceholderText("{}内容会显示在这里。".format(channel)); self.outputs[channel] = box; self.tabs.addTab(box, channel)

    def campaign_text(self) -> str:
        return self.main.current_campaign or self.main.pages["今日活动"].output.toPlainText().strip()

    def generate_one(self):
        campaign = self.campaign_text()
        if not campaign:
            QMessageBox.warning(self, "请先生成活动", "请先在“今日活动”页生成活动方案。")
            return
        channel = self.channel.currentText(); profile = self.main.db.get_profile(self.main.user_id) or {}; settings = self.main.db.get_ai_settings(self.main.user_id)
        self.source.setText("正在生成 {}…".format(channel))
        self.main.run_task(lambda: generate_content(channel, campaign, profile, settings), lambda result: self.content_ready(channel, result))

    def generate_all(self):
        campaign = self.campaign_text()
        if not campaign:
            QMessageBox.warning(self, "请先生成活动", "请先在“今日活动”页生成活动方案。")
            return
        profile, settings = self.main.db.get_profile(self.main.user_id) or {}, self.main.db.get_ai_settings(self.main.user_id)
        self.source.setText("正在生成全部渠道内容…")
        self.main.run_task(lambda: {name: generate_content(name, campaign, profile, settings) for name in self.CHANNELS}, self.all_ready)

    def content_ready(self, channel, result):
        text, source = result; self.outputs[channel].setPlainText(text); self.source.setText("{}：{}".format(channel, source))
        self.main.db.save_content(self.main.user_id, channel, text, self.main.current_campaign_id)

    def all_ready(self, results):
        for channel, result in results.items(): self.content_ready(channel, result)
        self.source.setText("全部渠道内容已生成。")

    def copy_current(self):
        box = self.outputs[self.tabs.tabText(self.tabs.currentIndex())]
        copy_text(box.toPlainText()); self.source.setText("已复制到剪贴板。")


class ReplyPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main
        layout = QVBoxLayout(self); title = QLabel("评论回复助手"); title.setObjectName("title"); layout.addWidget(title)
        controls = QHBoxLayout(); self.kind, self.tone = QComboBox(), QComboBox()
        self.kind.addItems(("好评", "差评", "咨询", "催单")); self.tone.addItems(("诚恳", "活泼", "正式")); run, copy = QPushButton("生成回复"), secondary("复制回复")
        run.clicked.connect(self.generate); copy.clicked.connect(lambda: copy_text(self.output.toPlainText()))
        controls.addWidget(QLabel("类型")); controls.addWidget(self.kind); controls.addWidget(QLabel("语气")); controls.addWidget(self.tone); controls.addWidget(run); controls.addWidget(copy); layout.addLayout(controls)
        self.comment = QPlainTextEdit(); self.comment.setPlaceholderText("粘贴学生的评论、咨询或催单内容"); self.comment.setFixedHeight(130); layout.addWidget(self.comment)
        self.source = QLabel(); self.source.setObjectName("subtle"); layout.addWidget(self.source)
        self.output = QPlainTextEdit(); self.output.setPlaceholderText("回复话术会显示在这里。"); layout.addWidget(self.output, 1)

    def generate(self):
        comment = self.comment.toPlainText().strip()
        if not comment:
            QMessageBox.warning(self, "请输入评论", "请先粘贴需要回复的评论。")
            return
        profile, settings = self.main.db.get_profile(self.main.user_id) or {}, self.main.db.get_ai_settings(self.main.user_id)
        self.source.setText("正在生成…")
        self.main.run_task(lambda: generate_reply(comment, self.kind.currentText(), self.tone.currentText(), profile, settings), self.ready)

    def ready(self, result):
        text, source = result; self.output.setPlainText(text); self.source.setText("来源：" + source)


class RecordDialog(QDialog):
    def __init__(self, main, record: Optional[Dict[str, Any]] = None):
        super().__init__(main); self.main, self.record = main, record or {}
        self.setWindowTitle("记录活动数据"); self.setMinimumWidth(500)
        form = QFormLayout(self)
        self.name = QLineEdit(self.record.get("campaign_name", self.default_name()))
        self.channels = QLineEdit("，".join(self.record.get("publish_channels", [])))
        self.publish_time = QLineEdit(self.record.get("publish_time", datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.coupons, self.visitors = QSpinBox(), QSpinBox(); self.sales = QDoubleSpinBox(); self.feedback = QPlainTextEdit(self.record.get("feedback", ""))
        self.coupons.setRange(0, 999999); self.visitors.setRange(0, 999999); self.sales.setRange(0, 99999999); self.sales.setDecimals(2)
        self.coupons.setValue(int(self.record.get("coupon_used", 0))); self.visitors.setValue(int(self.record.get("visitor_count", 0))); self.sales.setValue(float(self.record.get("sales_amount", 0)))
        form.addRow("活动名称", self.name); form.addRow("发布渠道", self.channels); form.addRow("发布时间", self.publish_time); form.addRow("优惠券核销数", self.coupons); form.addRow("到店人数", self.visitors); form.addRow("活动销售额", self.sales); form.addRow("用户反馈", self.feedback)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def default_name(self):
        text = self.main.current_campaign
        return next((x.split("：", 1)[1] for x in text.splitlines() if x.startswith("活动名称：")), "未命名活动") if text else ""

    def value(self):
        plan = self.record.get("campaign_plan", self.main.current_campaign or "活动数据补录")
        profile, weather, _cal, tags, _slot = self.main.context(full=True)
        channels = [x.strip() for x in self.channels.text().replace("、", "，").replace(",", "，").split("，") if x.strip()]
        return {"campaign_name": self.name.text().strip() or "未命名活动", "campaign_plan": plan, "node_tags": self.record.get("node_tags", tags), "weather_snapshot": self.record.get("weather_snapshot", weather), "publish_channels": channels, "publish_time": self.publish_time.text().strip(), "coupon_used": self.coupons.value(), "visitor_count": self.visitors.value(), "sales_amount": self.sales.value(), "feedback": self.feedback.toPlainText().strip()}


class ReviewPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main; self.records = []
        layout = QVBoxLayout(self); title = QLabel("数据复盘"); title.setObjectName("title"); layout.addWidget(title)
        buttons = QHBoxLayout(); add, edit, refresh = QPushButton("记录活动数据"), secondary("编辑选中记录"), secondary("刷新近 7 天")
        add.clicked.connect(self.add); edit.clicked.connect(self.edit); refresh.clicked.connect(self.refresh); buttons.addWidget(add); buttons.addWidget(edit); buttons.addWidget(refresh); layout.addLayout(buttons)
        self.summary = QLabel(); self.summary.setObjectName("subtle"); layout.addWidget(self.summary)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(("活动", "创建时间", "渠道", "核销", "到店", "销售额")); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.table, 1)

    def refresh(self):
        self.records = self.main.db.list_campaigns(self.main.user_id, days=7)
        self.table.setRowCount(len(self.records)); coupons = visitors = 0; sales = 0.0
        for row, item in enumerate(self.records):
            coupons += item["coupon_used"]; visitors += item["visitor_count"]; sales += item["sales_amount"]
            values = (item["campaign_name"], item["created_at"][:16].replace("T", " "), "、".join(item["publish_channels"]), str(item["coupon_used"]), str(item["visitor_count"]), "{:.2f}".format(item["sales_amount"]))
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(value))
        self.summary.setText("近 7 天：{} 个活动，核销 {}，到店 {}，活动销售额 {:.2f} 元。建议结合反馈保留高到店时段和渠道。".format(len(self.records), coupons, visitors, sales))

    def add(self):
        dialog = RecordDialog(self.main)
        if dialog.exec_():
            campaign_id = self.main.db.save_campaign(self.main.user_id, dialog.value())
            self.main.current_campaign_id = campaign_id; self.refresh()

    def edit(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            QMessageBox.information(self, "请选择记录", "请先选中一行活动记录。")
            return
        record = self.records[row]; dialog = RecordDialog(self.main, record)
        if dialog.exec_(): self.main.db.save_campaign(self.main.user_id, dialog.value(), record["id"]); self.refresh()


class SettingsPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main
        outer = QVBoxLayout(self); scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        content = QWidget(); scroll.setWidget(content); layout = QVBoxLayout(content)
        profile_group, profile_layout = card("店铺信息"); self.profile_form = ProfileForm(main.db.get_profile(main.user_id)); save_profile = QPushButton("保存店铺信息"); save_profile.clicked.connect(self.save_profile); profile_layout.addWidget(self.profile_form); profile_layout.addWidget(save_profile); layout.addWidget(profile_group)
        ai_group, ai_layout = card("AI API 设置（OpenAI Chat Completions 兼容）")
        ai_form = QFormLayout(); settings = main.db.get_ai_settings(main.user_id)
        self.base_url, self.api_key, self.model = QLineEdit(settings["base_url"]), QLineEdit(), QLineEdit(settings["model"])
        self.api_key.setPlaceholderText("已保存" if settings["api_key"] else "sk-…"); self.api_key.setEchoMode(QLineEdit.Password)
        self.temperature, self.max_tokens = QDoubleSpinBox(), QSpinBox(); self.temperature.setRange(0, 2); self.temperature.setSingleStep(0.1); self.temperature.setValue(settings["temperature"]); self.max_tokens.setRange(100, 16000); self.max_tokens.setValue(settings["max_tokens"])
        self.streaming = QCheckBox("启用流式请求"); self.streaming.setChecked(settings["stream"])
        ai_form.addRow("Base URL", self.base_url); ai_form.addRow("API Key", self.api_key); ai_form.addRow("模型", self.model); ai_form.addRow("Temperature", self.temperature); ai_form.addRow("最大输出长度", self.max_tokens); ai_form.addRow(self.streaming)
        ai_layout.addLayout(ai_form); ai_actions = QHBoxLayout(); save_ai, test_ai = QPushButton("保存 AI 设置"), secondary("测试连接")
        save_ai.clicked.connect(self.save_ai); test_ai.clicked.connect(self.test_ai); ai_actions.addWidget(save_ai); ai_actions.addWidget(test_ai); ai_layout.addLayout(ai_actions); self.ai_status = QLabel("API Key 已使用 Windows 凭据保护，界面不会回显。") ; self.ai_status.setObjectName("subtle"); ai_layout.addWidget(self.ai_status); layout.addWidget(ai_group)
        cal_group, cal_layout = card("校历配置与分析")
        self.calendar_text = QPlainTextEdit(); self.calendar_text.setPlaceholderText("手动粘贴考试周、放假、开学、上下课或活动信息") ; self.calendar_text.setFixedHeight(150)
        self.calendar_link = QLineEdit(); self.calendar_link.setPlaceholderText("公开 HTTP(S) 校历链接（网页、PDF 或文件）")
        cal_layout.addWidget(self.calendar_text); cal_layout.addWidget(self.calendar_link)
        cal_actions = QHBoxLayout(); import_file, import_link, analyze = secondary("导入文件"), secondary("读取链接"), QPushButton("分析并保存校历")
        import_file.clicked.connect(self.import_file); import_link.clicked.connect(self.import_link); analyze.clicked.connect(self.analyze_calendar)
        for button in (import_file, import_link, analyze): cal_actions.addWidget(button)
        cal_layout.addLayout(cal_actions); self.calendar_result = QPlainTextEdit(); self.calendar_result.setReadOnly(True); self.calendar_result.setFixedHeight(130); cal_layout.addWidget(self.calendar_result); layout.addWidget(cal_group)
        nodes_group, nodes_layout = card("手动校园节点与天气")
        self.manual_nodes = QLineEdit(main.db.get_setting(main.user_id, "manual_nodes", "")); self.manual_nodes.setPlaceholderText("例如：社团招新，运动会，迎新")
        nodes_layout.addWidget(QLabel("默认天气为 Open-Meteo；首页可刷新天气或手动覆盖。")); nodes_layout.addWidget(self.manual_nodes); save_nodes = QPushButton("保存手动节点"); save_nodes.clicked.connect(lambda: main.db.set_setting(main.user_id, "manual_nodes", self.manual_nodes.text())); nodes_layout.addWidget(save_nodes); layout.addWidget(nodes_group); layout.addStretch()
        self.load_calendar()

    def refresh(self):
        latest = self.main.db.get_profile(self.main.user_id)
        if latest:
            self.profile_form.load_profile(latest)
        self.load_calendar()

    def save_profile(self):
        try:
            self.main.db.save_profile(self.main.user_id, self.profile_form.value()); self.main.refresh_all(); QMessageBox.information(self, "已保存", "店铺信息已保存。")
        except ValueError as exc: QMessageBox.warning(self, "无法保存", str(exc))

    def ai_values(self):
        old = self.main.db.get_ai_settings(self.main.user_id)
        return {"base_url": self.base_url.text().strip(), "api_key": self.api_key.text().strip() or old["api_key"], "model": self.model.text().strip(), "temperature": self.temperature.value(), "max_tokens": self.max_tokens.value(), "stream": self.streaming.isChecked()}

    def save_ai(self):
        values = self.ai_values()
        for key, value in (("ai_base_url", values["base_url"]), ("ai_model", values["model"]), ("ai_temperature", str(values["temperature"])), ("ai_max_tokens", str(values["max_tokens"])), ("ai_stream", "1" if values["stream"] else "0")):
            self.main.db.set_setting(self.main.user_id, key, value)
        if self.api_key.text().strip(): self.main.db.set_setting(self.main.user_id, "ai_api_key", self.api_key.text().strip(), secret=True)
        self.api_key.clear(); self.ai_status.setText("AI 设置已保存；Key 已脱敏保护。")

    def test_ai(self):
        values = self.ai_values(); self.ai_status.setText("正在测试连接…")
        self.main.run_task(lambda: AIClient(values).test_connection(), lambda result: self.ai_status.setText("连接成功：" + result), lambda message: self.ai_status.setText("连接失败：" + message))

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择校历", "", "校历文件 (*.txt *.md *.csv *.xlsx *.xls *.docx *.pdf *.png *.jpg *.jpeg *.webp)")
        if not path: return
        self.calendar_result.setPlainText("正在提取文件内容…")
        self.main.run_task(lambda: extract_file(path), self.import_ready, lambda message: self.calendar_result.setPlainText("导入失败：" + message))

    def import_link(self):
        url = self.calendar_link.text().strip()
        if not url: return QMessageBox.warning(self, "请输入链接", "请粘贴公开的 HTTP(S) 校历链接。")
        self.calendar_result.setPlainText("正在读取链接…")
        self.main.run_task(lambda: extract_url(url), self.link_ready, lambda message: self.calendar_result.setPlainText("读取失败：" + message))

    def import_ready(self, result):
        text, kind = result; self.calendar_text.setPlainText(text); self.calendar_result.setPlainText("已导入 {}，请检查内容后点击“分析并保存校历”。".format(kind))

    def link_ready(self, result):
        text, kind, url = result; self.calendar_link.setText(url); self.calendar_text.setPlainText(text); self.calendar_result.setPlainText("已读取 {}，请检查内容后点击“分析并保存校历”。".format(kind))

    def analyze_calendar(self):
        raw = self.calendar_text.toPlainText().strip(); profile = self.main.db.get_profile(self.main.user_id) or {}
        if not raw: return QMessageBox.warning(self, "没有校历内容", "请先手动输入、导入文件或读取链接。")
        school = profile.get("school_name", "未命名学校"); self.calendar_result.setPlainText("正在分析校历…")
        settings = self.main.db.get_ai_settings(self.main.user_id)
        self.main.run_task(lambda: analyze_calendar(raw, school, AIClient(settings)), lambda parsed: self.calendar_ready(raw, parsed), lambda message: self.calendar_result.setPlainText("分析失败：" + message))

    def calendar_ready(self, raw, parsed):
        source = "链接" if self.calendar_link.text().strip() else "手动录入"
        data = dict(parsed); data.update({"source_type": source, "source_ref": self.calendar_link.text().strip(), "raw_content": raw})
        self.main.db.save_calendar(self.main.user_id, data); self.calendar_result.setPlainText("来源：{}\n{}".format(parsed.get("source"), parsed["parsed_summary"])); self.main.refresh_all()

    def load_calendar(self):
        current = self.main.db.get_latest_calendar(self.main.user_id)
        if current:
            self.calendar_result.setPlainText("已保存校历\n" + current.get("parsed_summary", ""))


class MainWindow(QMainWindow):
    def __init__(self, db: Database, user: Dict[str, Any]):
        super().__init__(); self.db, self.user_id, self.username = db, user["id"], user["username"]
        self.current_campaign, self.current_campaign_id, self._tasks = "", None, []
        self.setWindowTitle(APP_NAME); self.resize(1240, 780)
        central = QWidget(); self.setCentralWidget(central); shell = QHBoxLayout(central); shell.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget(); self.nav.setFixedWidth(175); self.stack = QStackedWidget(); shell.addWidget(self.nav); shell.addWidget(self.stack, 1)
        self.pages = {"首页": HomePage(self), "今日活动": CampaignPage(self), "内容生成": ContentPage(self), "评论回复": ReplyPage(self), "数据复盘": ReviewPage(self), "设置": SettingsPage(self)}
        for name, page in self.pages.items(): self.nav.addItem(name); self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.changed); self.nav.setCurrentRow(0)

    def run_task(self, fn: Callable[[], Any], success: Callable[[Any], None], failure: Optional[Callable[[str], None]] = None):
        thread, worker = QThread(self), TaskWorker(fn); worker.moveToThread(thread)
        thread.started.connect(worker.run); worker.finished.connect(success); worker.failed.connect(failure or self.show_error)
        worker.finished.connect(thread.quit); worker.failed.connect(thread.quit); thread.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._tasks.remove((thread, worker)) if (thread, worker) in self._tasks else None)
        self._tasks.append((thread, worker)); thread.start()

    def show_error(self, message: str): QMessageBox.warning(self, "操作失败", message)

    def changed(self, index: int):
        if index < 0: return
        self.stack.setCurrentIndex(index); page = self.stack.currentWidget()
        if hasattr(page, "refresh"): page.refresh()

    def go(self, name: str): self.nav.setCurrentRow(list(self.pages).index(name))

    def weather_context(self):
        raw = self.db.get_setting(self.user_id, "weather_cache", "")
        if raw:
            try: return json.loads(raw)
            except json.JSONDecodeError: pass
        profile = self.db.get_profile(self.user_id) or {}
        return {"city": profile.get("city", "未设置"), "weather": "晴", "temperature": 23, "high": 26, "low": 18, "precipitation_probability": 10, "tags": [], "source": "本地演示天气（请刷新）"}

    def context(self, full: bool = False):
        profile = self.db.get_profile(self.user_id) or {}
        weather, calendar = self.weather_context(), self.db.get_latest_calendar(self.user_id) or {"parsed_summary": "尚未配置校历"}
        manual = self.db.get_setting(self.user_id, "manual_nodes", "").replace("、", "，").replace(",", "，").split("，")
        tags, slot = campus_nodes(weather, calendar, manual)
        if full: return profile, weather, calendar, tags, slot
        return weather, calendar, tags, slot

    def refresh_all(self):
        for page in self.pages.values():
            if hasattr(page, "refresh"): page.refresh()


def main():
    app = QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setFont(QFont("Microsoft YaHei UI", 10)); app.setStyleSheet(STYLE)
    db = Database(); user_id = db.restore_session(); user = db.get_user(user_id) if user_id else None
    if not user:
        login = LoginDialog(db)
        if not login.exec_(): return 0
        user = login.user
    window = MainWindow(db, user)
    if not db.get_profile(user["id"]):
        profile = ProfileDialog(window, first_run=True)
        profile.exec_()
    window.refresh_all(); window.show()
    return app.exec_()


if __name__ == "__main__":
    from app_v2 import main as v2_main
    sys.exit(v2_main())
