from pydantic import BaseModel, ConfigDict


class UserCapabilitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflows: tuple[str, ...] = (
        "研究小红书账号或笔记，并形成研究材料",
        "基于研究材料制定内容策略与选题机会",
        "基于策略和选题创作草稿",
        "根据具体反馈持续修改已有草稿",
        "复盘本系统中已发布笔记的表现",
    )
    unsupported: tuple[str, ...] = (
        "代替用户登录或操作小红书账号",
        "自动发布、点赞、评论、关注或私信",
        "分析未绑定到本系统 Published Note 的外部笔记私域表现",
        "绕过账号、workspace 或数据访问边界",
    )

    def prompt_text(self) -> str:
        supported = "\n".join(f"- {item}" for item in self.workflows)
        unsupported = "\n".join(f"- {item}" for item in self.unsupported)
        return f"支持能力：\n{supported}\n不支持边界：\n{unsupported}"


AgentCapabilities = UserCapabilitySnapshot
CAPABILITIES = UserCapabilitySnapshot()
