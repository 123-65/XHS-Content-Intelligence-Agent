from app.enums.keyword import KeywordCategory
from app.models.account import AccountProfile
from app.models.keyword_seed import KeywordSeed
from app.repositories.keyword_seed_repo import KeywordSeedRepository
from app.schemas.keyword_seed import KeywordGenerateRequest, KeywordSeedCreate
from sqlalchemy.orm import Session


KEYWORD_TEMPLATES: dict[KeywordCategory, tuple[str, ...]] = {
    KeywordCategory.USER_DEMAND: (
        "{audience} 如何学习 {domain}",
        "{audience} {domain} 入门路线",
        "{audience} 做 {product} 从哪里开始",
        "{domain} 新手常见问题",
        "{domain} 学不会怎么办",
    ),
    KeywordCategory.MEDIA_EXPRESSION: (
        "{domain} 学习路线",
        "{domain} 避坑清单",
        "{domain} 项目实战",
        "{domain} 图文教程",
        "{domain} 复盘笔记",
    ),
    KeywordCategory.CONVERSION_SIGNAL: (
        "{product} 资料包",
        "{product} 项目模板",
        "{domain} 简历项目",
        "{domain} 求职作品集",
        "{domain} 咨询",
    ),
    KeywordCategory.PEER_IDENTITY: (
        "普通大学生 {domain}",
        "转码初学者 {domain}",
        "零基础 {domain}",
        "应届生 {domain}",
        "{persona} {domain}",
    ),
}


class KeywordSeedService:
    """关键词池业务服务。"""

    def __init__(self, db: Session):
        """初始化关键词池服务。"""
        self.repo = KeywordSeedRepository(db)

    def generate_keywords(self, data: KeywordGenerateRequest) -> list[KeywordSeed]:
        """基于账号画像用规则模板生成关键词。"""
        account = self._get_account_or_raise(data.account_id)
        context = self._build_context(account)
        seeds = [
            self._build_seed(data.account_id, category, template, context)
            for category, templates in KEYWORD_TEMPLATES.items()
            for template in templates[: data.limit_per_category]
        ]
        return self.repo.create_many(self._deduplicate(seeds))

    def list_keywords(self, account_id: int, category: str | None = None) -> list[KeywordSeed]:
        """查询账号关键词列表。"""
        self._get_account_or_raise(account_id)
        return self.repo.list_by_account(account_id=account_id, category=category)

    def _get_account_or_raise(self, account_id: int) -> AccountProfile:
        """查询账号配置，不存在时抛出业务错误。"""
        account = self.repo.get_account(account_id)
        if account:
            return account
        raise ValueError("账号配置不存在")

    def _build_context(self, account: AccountProfile) -> dict[str, str]:
        """构建关键词模板上下文。"""
        domain = account.content_domain or account.positioning[:24] or "知识成长"
        return {
            "domain": domain,
            "audience": self._first_phrase(account.target_audience, "目标用户"),
            "persona": self._first_phrase(account.persona, account.account_name),
            "product": account.main_product or account.monetization_goal or account.business_model or "核心产品",
        }

    def _build_seed(
        self,
        account_id: int,
        category: KeywordCategory,
        template: str,
        context: dict[str, str],
    ) -> KeywordSeedCreate:
        """根据模板构造关键词。"""
        keyword = template.format(**context)
        return KeywordSeedCreate(
            account_id=account_id,
            keyword=keyword,
            category=category,
            reason=f"基于账号画像和 {category.value} 分类规则生成",
            confidence=0.82,
            raw_snapshot={"template": template, "context": context, "category": category.value},
        )

    def _deduplicate(self, seeds: list[KeywordSeedCreate]) -> list[KeywordSeedCreate]:
        """按分类和关键词去重。"""
        seen = set()
        result = []
        for seed in seeds:
            key = (seed.category, seed.keyword)
            if key in seen:
                continue
            seen.add(key)
            result.append(seed)
        return result

    def _first_phrase(self, text: str | None, fallback: str) -> str:
        """提取逗号分隔文本的第一个短语。"""
        return next((part.strip() for part in (text or "").replace("、", ",").split(",") if part.strip()), fallback)
