"""面向校历分析的 AI 客户端包装。"""
from .ai_request import complete, configured


class AIClient:
    def __init__(self, settings):
        self.settings = settings

    @property
    def is_configured(self):
        return configured(self.settings)

    def complete(self, prompt, stream=False):
        return complete(self.settings, prompt, stream=stream)

    def test_connection(self):
        return complete(self.settings, "请只回复：连接成功", system="你是连通性测试助手。")
