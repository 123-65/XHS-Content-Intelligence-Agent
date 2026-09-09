from dataclasses import dataclass, field
from typing import Any


BLOCKED_ACTIONS = {
    "自动点赞": "BLOCK_AUTO_LIKE",
    "自动评论": "BLOCK_AUTO_COMMENT",
    "自动关注": "BLOCK_AUTO_FOLLOW",
    "自动私信": "BLOCK_AUTO_DM",
    "绕过验证码": "BLOCK_CAPTCHA_BYPASS",
    "绕过风控": "BLOCK_RISK_CONTROL_BYPASS",
    "虚构经历": "BLOCK_FAKE_EXPERIENCE",
    "夸大收益": "BLOCK_EXAGGERATED_REVENUE",
    "保 offer": "BLOCK_GUARANTEED_OFFER",
    "guarantee offer": "BLOCK_GUARANTEED_OFFER",
    "bypass captcha": "BLOCK_CAPTCHA_BYPASS",
    "auto like": "BLOCK_AUTO_LIKE",
    "auto comment": "BLOCK_AUTO_COMMENT",
    "auto follow": "BLOCK_AUTO_FOLLOW",
    "auto dm": "BLOCK_AUTO_DM",
}

BLOCKED_TOOL_NAMES = {
    "auto_like",
    "auto_comment",
    "auto_follow",
    "auto_dm",
    "captcha_bypass",
    "risk_control_bypass",
}


@dataclass(frozen=True)
class GuardrailDecision:
    """安全护栏判断结果。"""

    allowed: bool
    reason: str | None = None
    codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class GuardrailPolicy:
    """Agent 工具调用安全护栏。"""

    def inspect(self, tool_name: str, payload: dict) -> GuardrailDecision:
        """检查工具名和入参是否命中禁止动作。"""
        blocked_codes = self._blocked_tool_codes(tool_name) | self._blocked_text_codes(payload)
        if blocked_codes:
            return GuardrailDecision(False, "Risk blocked by GuardrailPolicy", sorted(blocked_codes), {"tool_name": tool_name})
        return GuardrailDecision(True)

    def _blocked_tool_codes(self, tool_name: str) -> set[str]:
        """根据工具名识别禁止工具。"""
        return {"BLOCK_FORBIDDEN_TOOL"} if tool_name in BLOCKED_TOOL_NAMES else set()

    def _blocked_text_codes(self, payload: dict) -> set[str]:
        """根据入参文本识别禁止表达。"""
        text = str(payload).lower()
        return {code for phrase, code in BLOCKED_ACTIONS.items() if phrase.lower() in text}
