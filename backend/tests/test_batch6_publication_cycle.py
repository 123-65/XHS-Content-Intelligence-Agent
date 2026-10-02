import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.publication import (
    ConfirmStrategyCandidateInput,
    MetricWindow,
    PostPublishReviewInput,
    PrivateMetricsInput,
    PublishPackageInput,
    PublishedNoteBindingInput,
)
from app.services.post_publish_review_v0_sev import PostPublishReviewService
from app.services.private_metrics_sev import PrivateMetricsService
from app.services.publish_package_sev import PublishPackageService
from app.services.published_metrics_sev import PublishedMetricsService
from app.services.published_note_binding_sev import PublishedNoteBindingService
from app.services.strategy_memory_sev import StrategyMemoryService


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


class FakeCollector:
    """模拟正式采集器返回的单篇笔记实测结果。"""

    def collect_public_note_metrics(self, note_url):
        """返回固定的平台标识与公开指标。"""
        return {
            "platform_note_id": "xhs-note-88",
            "note_url": note_url,
            "source": "fake-xhs-provider",
            "provenance": "MEASURED",
            "metrics": {"like_count": 120, "collect_count": 43, "comment_count": 8, "share_count": 5},
        }


class FakeLLMClient:
    """模拟只负责复盘解释的大模型客户端。"""

    def generate_structured(self, **kwargs):
        """返回包含证据引用和待确认候选的结构化复盘。"""
        return SimpleNamespace(
            data={
                "observed_results": ["公开收藏数为 43"],
                "public_performance_analysis": "收藏表现高于其他公开互动。",
                "optional_conversion_analysis": None,
                "strategy_alignment": "与清单型内容方向一致。",
                "what_worked": ["清单结构"],
                "what_did_not_work": [],
                "uncertainties": ["未提供完整私域指标"],
                "evidence_refs": [
                    {"kind": "published_note", "id": 31},
                    {"kind": "public_metric_snapshot", "id": 41},
                    {"kind": "private_metric_snapshot", "id": 51},
                ],
                "strategy_candidates": [
                    {
                        "candidate_index": 0,
                        "statement": "继续验证清单型内容是否更易被收藏。",
                        "scope": "下一轮内容实验",
                        "supporting_refs": [{"kind": "public_metric_snapshot", "id": 41}],
                        "contradicting_refs": [],
                        "confidence_context": "当前仅有一篇笔记。",
                        "status": "PROPOSED",
                    }
                ],
            },
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0.01,
            raw_response_id="fake-review-response",
        )


class ReviewPolicyClient:
    def __init__(self, data=None):
        self.calls = []
        self.data = data

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=self.data or {
            "observed_results": [],
            "public_performance_analysis": "公开指标未知。",
            "optional_conversion_analysis": "用户归因私域数据可用。",
            "strategy_alignment": "待继续观察。",
            "what_worked": [],
            "what_did_not_work": [],
            "uncertainties": ["公开指标未知"],
            "evidence_refs": [],
            "strategy_candidates": [],
        })


def _grounded_review(refs=None, candidate_refs=None):
    refs = refs or []
    candidate_refs = candidate_refs or []
    return {
        "observed_results": [], "public_performance_analysis": "公开指标未知。",
        "optional_conversion_analysis": "私信 3，微信 1，其余未知。", "strategy_alignment": "待观察。",
        "what_worked": [], "what_did_not_work": [], "uncertainties": ["公开指标未知"],
        "evidence_refs": refs,
        "strategy_candidates": [{
            "candidate_index": 0, "statement": "继续测试", "scope": "下一轮", "status": "PROPOSED",
            "supporting_refs": candidate_refs, "contradicting_refs": [], "confidence_context": "样本有限",
        }],
    }


def test_post_publish_review_grounding_accepts_resolved_refs_and_rejects_unretrieved_refs():
    allowed = [{"kind": "published_note", "id": 592}, {"kind": "private_metric_snapshot", "id": 416}]
    service = PostPublishReviewService(None, llm_client=ReviewPolicyClient(_grounded_review(allowed, [allowed[1]])), repository=SimpleNamespace())
    result = service.review_semantic({"evidence_refs": allowed})
    assert [(item.kind, item.id) for item in result.evidence_refs] == [("published_note", 592), ("private_metric_snapshot", 416)]

    unauthorized = PostPublishReviewService(None, llm_client=ReviewPolicyClient(_grounded_review([{"kind": "research_report", "id": 999}])), repository=SimpleNamespace())
    with pytest.raises(ValueError, match="无效 EvidenceRefs"):
        unauthorized.review_semantic({"evidence_refs": allowed})


def test_post_publish_review_empty_grounding_allows_no_claims_but_rejects_model_refs():
    empty = PostPublishReviewService(None, llm_client=ReviewPolicyClient(_grounded_review()), repository=SimpleNamespace())
    assert empty.review_semantic({"evidence_refs": []}).evidence_refs == []

    claimed = PostPublishReviewService(None, llm_client=ReviewPolicyClient(_grounded_review(candidate_refs=[{"kind": "published_note", "id": 592}])), repository=SimpleNamespace())
    with pytest.raises(ValueError, match="无效 EvidenceRefs"):
        claimed.review_semantic({"evidence_refs": []})


def test_post_publish_review_uses_task_specific_execution_policy(monkeypatch):
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_model", "default-strong")
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_timeout_seconds", 30)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_model", "qwen3.8-flash")
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_timeout_seconds", 120)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_enable_thinking", False)
    client = ReviewPolicyClient()

    PostPublishReviewService(None, llm_client=client, repository=SimpleNamespace()).review_semantic({"evidence_refs": []})

    call = client.calls[0]
    assert call["model"] == "qwen3.8-flash"
    assert call["timeout_seconds"] == 120
    assert call["extra_body"] == {"enable_thinking": False}
    assert call["prompt_key"] == "post_publish_review_semantic"
    assert call["prompt_version"] == "v2"


def test_post_publish_review_policy_falls_back_to_global_without_thinking_override(monkeypatch):
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_model", "default-strong")
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_timeout_seconds", 30)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_model", None)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_timeout_seconds", None)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.settings.llm_post_publish_review_enable_thinking", None)

    assert PostPublishReviewService._execution_policy() == {
        "model": "default-strong",
        "timeout_seconds": 30,
    }


class FakePublicationRepository:
    """在内存中记录发布闭环的持久化副作用。"""

    def __init__(self):
        """准备账号、最终稿和空的闭环记录。"""
        self.account = SimpleNamespace(id=7)
        self.draft = SimpleNamespace(
            id=11,
            account_id=7,
            experiment_id=101,
            recommended_title="最终标题",
            title="旧标题",
            body_text="最终正文",
            body="旧正文",
            tag_list=["Agent", "求职"],
            tags=[],
            cta_text="欢迎交流",
            cta="",
            version=3,
        )
        self.version = SimpleNamespace(id=12, draft_id=11, version=3, draft_snapshot={"title": "链路标题", "body": "链路正文", "tags": ["Agent", "求职"], "cta": "欢迎交流"})
        self.package = None
        self.note = None
        self.public_snapshots = []
        self.private_snapshots = []
        self.review = None
        self.memories = []

    def get_account(self, object_id):
        """按标识读取测试账号。"""
        return self.account if object_id == self.account.id else None

    def get_draft(self, object_id):
        """按标识读取最终稿。"""
        return self.draft if object_id == self.draft.id else None

    def get_draft_version(self, object_id):
        """按标识读取测试 Draft Version。"""
        return self.version if object_id == self.version.id else None

    def get_package(self, object_id):
        """按标识读取人工发布包。"""
        return self.package if self.package and object_id == self.package.id else None

    def get_note(self, object_id):
        """按标识读取已绑定笔记。"""
        return self.note if self.note and object_id == self.note.id else None

    def get_review(self, object_id):
        """按标识读取发布后复盘。"""
        return self.review if self.review and object_id == self.review.id else None

    def create_package(self, account_id, draft, version, notes):
        """记录不含自动发布能力的人工发布包。"""
        self.package = SimpleNamespace(
            id=21,
            account_id=account_id,
            draft_id=draft.id,
            draft_version_id=version.id,
            version_number=version.version,
            title=version.draft_snapshot["title"],
            body=version.draft_snapshot["body"],
            tags=version.draft_snapshot["tags"],
            stats={"draft_version_ref": "draft:11:v3", "auto_publish": False},
            created_at=datetime.now(timezone.utc),
        )
        return self.package

    def create_published_note(self, package, draft, note_url, published_at):
        """记录 Draft Version 与真实平台笔记的绑定。"""
        self.note = SimpleNamespace(
            id=31,
            account_id=package.account_id,
            experiment_id=draft.experiment_id,
            draft_id=draft.id,
            draft_version_id=package.draft_version_id,
            publish_url=note_url,
            published_at=published_at,
            created_at=datetime.now(timezone.utc),
            raw_snapshot={"draft_version_ref": "draft:11:v3", "platform_note_id": "xhs-note-88"},
        )
        return self.note

    def create_public_metrics(self, note_id, window, metrics, source, raw):
        """追加公开指标快照。"""
        record = SimpleNamespace(
            id=41,
            published_note_id=note_id,
            snapshot_window=window.label,
            collected_at=datetime.now(timezone.utc),
            like_count=metrics["like_count"],
            collect_count=metrics["collect_count"],
            comment_count=metrics["comment_count"],
            share_count=metrics["share_count"],
            raw_snapshot={"provenance": "MEASURED", "source": source},
        )
        self.public_snapshots.append(record)
        return record

    def create_private_metrics(self, data):
        """只记录用户实际填写的私域字段。"""
        values = {name: getattr(data, name) for name in ("dm_count", "wechat_add_count", "consultation_count", "deal_count", "revenue") if getattr(data, name) is not None}
        record = SimpleNamespace(
            id=51,
            published_note_id=data.published_note_ref,
            snapshot_window=data.window.label,
            collected_at=datetime.now(timezone.utc),
            raw_snapshot={"provided_fields": list(values), "values": values, "provenance": "USER_ATTRIBUTED"},
        )
        self.private_snapshots.append(record)
        return record

    def list_public_metrics(self, note_id):
        """读取指定笔记的公开快照。"""
        return [item for item in self.public_snapshots if item.published_note_id == note_id]

    def list_private_metrics(self, note_id):
        """读取指定笔记的私域快照。"""
        return [item for item in self.private_snapshots if item.published_note_id == note_id]

    def create_post_review(self, note, account_id, result, llm_result):
        """保存复盘及仍处于待确认状态的策略候选。"""
        candidates = [item.model_copy(update={"created_from_review": 61}).model_dump(mode="json") for item in result.strategy_candidates]
        self.review = SimpleNamespace(id=61, account_id=account_id, review_type="POST_PUBLISH_REVIEW_V1", action_suggestions=candidates)
        return self.review

    def create_memory(self, account_id, review_id, candidate):
        """记录经过人工确认的策略记忆。"""
        memory = SimpleNamespace(id=71, account_id=account_id, review_id=review_id, candidate=candidate)
        self.memories.append(memory)
        return memory


def test_manual_publication_to_confirmed_strategy_memory_cycle():
    """验证完整人工发布闭环以及策略记忆确认门禁。"""
    repo = FakePublicationRepository()
    collector = FakeCollector()
    now = datetime.now(timezone.utc)
    window = MetricWindow(label="D7", window_start=now, window_end=now + timedelta(days=7))

    package = PublishPackageService(None, repository=repo).create_package(PublishPackageInput(account_id=7, draft_version_id=12))
    assert package.draft_version_id == 12
    assert repo.package.stats["auto_publish"] is False

    note = PublishedNoteBindingService(None, collector=collector, repository=repo).bind(
        PublishedNoteBindingInput(account_id=7, publish_package_ref=21, publish_url="https://www.xiaohongshu.com/explore/xhs-note-88", published_at=now)
    )
    assert note.platform_note_id == "xhs-note-88"

    public = PublishedMetricsService(None, collector=collector, repository=repo).snapshot(note.published_note_ref, window)
    assert public.provenance == "MEASURED"
    assert public.metrics["collect_count"] == 43

    private = PrivateMetricsService(None, repository=repo).record(
        PrivateMetricsInput(account_id=7, published_note_ref=31, window=window, dm_count=4)
    )
    assert private.provenance == "USER_ATTRIBUTED"
    assert private.metrics["dm_count"] == 4
    assert private.metrics["deal_count"] is None

    review = PostPublishReviewService(None, llm_client=FakeLLMClient(), repository=repo).review(
        PostPublishReviewInput(account_id=7, published_note_ref=31, strategy_ref="strategy:9", opportunity_ref=5)
    )
    assert review.strategy_candidates[0].status == "PROPOSED"
    assert repo.memories == []

    memory_service = StrategyMemoryService(None, repository=repo)
    waiting = memory_service.confirm_candidate(ConfirmStrategyCandidateInput(account_id=7, review_ref=61, candidate_index=0, confirmed=False))
    assert waiting.status == "WAITING_CONFIRMATION"
    assert repo.memories == []
    saved = memory_service.confirm_candidate(ConfirmStrategyCandidateInput(account_id=7, review_ref=61, candidate_index=0, confirmed=True))
    assert saved.status == "SAVED"
    assert repo.memories[0].candidate["status"] == "CONFIRMED"


def test_batch6_owner_and_boundary_guards():
    """验证旧 Owner、自动发布和大模型直写记忆均未残留。"""
    service_text = "\n".join(path.read_text(encoding="utf-8") for path in (APP_ROOT / "services").glob("*.py"))
    assert service_text.count("class PostPublishReviewService:") == 1
    assert service_text.count("class StrategyMemoryService:") == 1
    assert "class PostPublishService:" not in service_text
    assert "class PostPublishReviewV0Service:" not in service_text
    assert "class StrategyMemoryConfirmationService:" not in service_text
    assert "auto_publish(" not in service_text

    review_source = (APP_ROOT / "services" / "post_publish_review_v0_sev.py").read_text(encoding="utf-8")
    memory_source = (APP_ROOT / "services" / "strategy_memory_sev.py").read_text(encoding="utf-8")
    assert "XiaohongshuMcpProvider" not in review_source
    assert "create_memory" not in review_source
    assert "LLMClient" not in memory_source
    assert "confirmed" in memory_source


def test_batch6_new_functions_have_chinese_descriptions():
    """确保本批新增或重写的函数与类都保留中文说明。"""
    paths = [
        APP_ROOT / "repositories" / "publication_repo.py",
        APP_ROOT / "schemas" / "publication.py",
        APP_ROOT / "services" / "post_publish_review_v0_sev.py",
        APP_ROOT / "services" / "private_metrics_sev.py",
        APP_ROOT / "services" / "publish_package_sev.py",
        APP_ROOT / "services" / "published_metrics_sev.py",
        APP_ROOT / "services" / "published_note_binding_sev.py",
        APP_ROOT / "services" / "strategy_memory_sev.py",
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                assert doc and any("\u4e00" <= char <= "\u9fff" for char in doc), f"{path.name}:{node.name} 缺少中文说明"
