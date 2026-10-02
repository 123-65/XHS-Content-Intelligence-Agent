import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.analysis.competitor.engine import CompetitorAnalysisError
from app.analysis.competitor.evidence import CompetitorEvidenceBuilder
from app.analysis.competitor.grounding import CompetitorGroundingValidator
from app.analysis.competitor.llm_analyzer import LLMStructuredCompetitorAnalyzer
from evals.baselines.research_rule_baseline import RuleBaselineCompetitorAnalyzer
from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult
from app.core.database import SessionLocal
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote


ACCOUNT_ID = 2
ACCOUNT_IDS = [1697, 1698, 1699]
NOTE_IDS = list(range(6483, 6495))
COMMENT_IDS = list(range(6553, 6573))
REAL_PROVIDER = "xiaohongshu_mcp"
RESULT_DIR = Path(__file__).resolve().parents[1] / "results"

SCORE_FIELDS = [
    "persona_accuracy",
    "audience_accuracy",
    "content_pillar_quality",
    "comment_demand_accuracy",
    "evidence_grounding",
    "specificity",
    "actionability",
]


def load_evidence() -> CompetitorEvidence:
    """从已验收记录构建固定真实 Evidence，不触发重新采集。"""
    with SessionLocal() as db:
        accounts = list(
            db.scalars(select(CompetitorAccount).where(CompetitorAccount.id.in_(ACCOUNT_IDS)).order_by(CompetitorAccount.id))
        )
        notes = list(db.scalars(select(CompetitorNote).where(CompetitorNote.id.in_(NOTE_IDS)).order_by(CompetitorNote.id)))
        comments = list(
            db.scalars(select(CompetitorComment).where(CompetitorComment.id.in_(COMMENT_IDS)).order_by(CompetitorComment.id))
        )

    _assert_real_records("account", accounts, ACCOUNT_IDS)
    _assert_real_records("note", notes, NOTE_IDS)
    _assert_real_records("comment", comments, COMMENT_IDS)
    evidence = CompetitorEvidenceBuilder().build(ACCOUNT_ID, accounts, notes, comments)
    if evidence.used_account_ids != ACCOUNT_IDS or evidence.used_note_ids != NOTE_IDS or evidence.used_comment_ids != COMMENT_IDS:
        raise RuntimeError("REAL_EVIDENCE_ID_MISMATCH")
    return evidence


def _assert_real_records(kind: str, records: list, expected_ids: list[int]) -> None:
    actual_ids = [item.id for item in records]
    if actual_ids != expected_ids:
        raise RuntimeError(f"{kind.upper()}_SNAPSHOT_INCOMPLETE: expected={expected_ids}, actual={actual_ids}")
    invalid = [
        item.id
        for item in records
        if item.account_id != ACCOUNT_ID or item.is_mock or item.source_type != "XHS_MCP" or item.provider_name != REAL_PROVIDER
    ]
    if invalid:
        raise RuntimeError(f"NON_REAL_{kind.upper()}_RECORDS: {invalid}")


def grounding_summary(evidence: CompetitorEvidence, result: CompetitorSemanticResult) -> dict:
    """复用生产校验，并输出盲评需要的引用计数。"""
    CompetitorGroundingValidator().validate(evidence, result)
    refs: list[tuple[str, int]] = []
    refs.extend((item.source_type, item.source_id) for item in result.persona.evidence)
    refs.extend((item.source_type, item.source_id) for item in result.follow_recommendation.evidence)
    for signal in [*result.conversion_signals, *result.risk_points]:
        refs.extend((item.source_type, item.source_id) for item in signal.evidence)
    refs.extend(("NOTE", note_id) for item in result.content_pillars for note_id in item.evidence_note_ids)
    refs.extend(("COMMENT", comment_id) for item in result.audience_demands for comment_id in item.representative_comment_ids)
    refs.extend(("NOTE", note_id) for item in result.high_performing_patterns for note_id in item.evidence_note_ids)
    refs.extend(("METRIC", metric.note_id) for item in result.high_performing_patterns for metric in item.metric_evidence)
    refs.extend(("NOTE", note_id) for note_id in result.content_style.evidence_note_ids)
    refs.extend(("NOTE", note_id) for item in result.content_opportunities for note_id in item.evidence_note_ids)
    refs.extend(("COMMENT", comment_id) for item in result.content_opportunities for comment_id in item.evidence_comment_ids)

    allowed = {
        "ACCOUNT": set(evidence.used_account_ids),
        "NOTE": set(evidence.used_note_ids),
        "COMMENT": set(evidence.used_comment_ids),
        "METRIC": set(evidence.used_note_ids),
        "OCR": set(evidence.ocr_note_ids),
    }
    invalid = [f"{kind}:{record_id}" for kind, record_id in refs if record_id not in allowed[kind]]
    return {
        "status": "PASSED" if not invalid else "FAILED",
        "valid_ref_count": len(refs) - len(invalid),
        "invalid_ref_count": len(invalid),
        "invalid_refs": invalid,
        "hallucinated_ids": sorted(set(invalid)),
    }


def build_blind_artifact(
    evidence: CompetitorEvidence,
    baseline: CompetitorSemanticResult,
    llm: CompetitorSemanticResult,
) -> dict:
    evidence_json = evidence.model_dump_json()
    baseline_payload = {
        "status": "SUCCESS",
        "result": baseline.model_dump(mode="json"),
        "grounding": grounding_summary(evidence, baseline),
    }
    llm_payload = {
        "status": "SUCCESS",
        "result": llm.model_dump(mode="json"),
        "grounding": grounding_summary(evidence, llm),
    }
    return _blind_artifact(evidence, baseline_payload, llm_payload)


def build_failed_blind_artifact(
    evidence: CompetitorEvidence,
    baseline: CompetitorSemanticResult,
    error_code: str,
    invalid_refs: list[str],
) -> dict:
    """记录真实 Analyzer 失败，不伪造缺失的语义结果。"""
    baseline_payload = {
        "status": "SUCCESS",
        "result": baseline.model_dump(mode="json"),
        "grounding": grounding_summary(evidence, baseline),
    }
    failed_payload = {
        "status": "FAILED",
        "error_code": error_code,
        "result": None,
        "grounding": {
            "status": "FAILED",
            "validation_mode": "fail_fast",
            "valid_ref_count": None,
            "invalid_ref_count": len(invalid_refs),
            "invalid_refs": invalid_refs,
            "hallucinated_ids": invalid_refs,
        },
    }
    return _blind_artifact(evidence, baseline_payload, failed_payload)


def _blind_artifact(evidence: CompetitorEvidence, baseline_payload: dict, candidate_payload: dict) -> dict:
    evidence_json = evidence.model_dump_json()
    first_is_baseline = hashlib.sha256(evidence_json.encode("utf-8")).digest()[0] % 2 == 0
    analysis_a, analysis_b = (
        (baseline_payload, candidate_payload) if first_is_baseline else (candidate_payload, baseline_payload)
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_summary": {
            "account_id": evidence.account_id,
            "used_account_ids": evidence.used_account_ids,
            "used_note_ids": evidence.used_note_ids,
            "used_comment_ids": evidence.used_comment_ids,
            "account_count": len(evidence.used_account_ids),
            "note_count": len(evidence.used_note_ids),
            "comment_count": len(evidence.used_comment_ids),
            "mock_records_included": 0,
            "redacted_titles": [
                {"note_id": note.id, "title": f"真实笔记 {index:02d}"}
                for index, note in enumerate(evidence.notes, start=1)
            ],
            "data_gaps": evidence.data_gaps,
        },
        "analysis_a": analysis_a,
        "analysis_b": analysis_b,
        "mapping_hidden": True,
    }


def score_template() -> dict:
    empty_scores = {field: None for field in SCORE_FIELDS}
    return {
        "analysis_a": {**empty_scores, "hallucination": None},
        "analysis_b": {**empty_scores, "hallucination": None},
        "overall_preference": None,
        "constraints": {
            "quality_score": "1-5",
            "hallucination": {"0": "none", "1": "minor", "2": "serious"},
            "overall_preference": ["A", "B", "TIE"],
        },
        "mapping_hidden": True,
    }


def render_html(artifact: dict) -> str:
    evidence = html.escape(json.dumps(artifact["evidence_summary"], ensure_ascii=False, indent=2))
    analysis_a = html.escape(json.dumps(artifact["analysis_a"], ensure_ascii=False, indent=2))
    analysis_b = html.escape(json.dumps(artifact["analysis_b"], ensure_ascii=False, indent=2))
    score_rows = "".join(
        f"<tr><td>{field}</td><td><input type='number' min='1' max='5'></td><td><input type='number' min='1' max='5'></td></tr>"
        for field in SCORE_FIELDS
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>竞品分析盲评 A/B</title>
  <style>
    body {{ margin: 0; background: #f4f6f8; color: #17202a; font: 14px/1.55 system-ui, sans-serif; }}
    main {{ max-width: 1440px; margin: auto; padding: 24px; }}
    h1 {{ margin: 0 0 18px; font-size: 24px; }}
    h2 {{ font-size: 16px; }}
    .band {{ margin-bottom: 18px; padding: 16px; border: 1px solid #dfe3e8; background: #fff; }}
    .columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    pre {{ overflow: auto; max-height: 720px; margin: 0; white-space: pre-wrap; word-break: break-word; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ padding: 10px; border: 1px solid #dfe3e8; text-align: left; }}
    input, select {{ width: 80px; box-sizing: border-box; }}
    @media (max-width: 820px) {{ .columns {{ grid-template-columns: 1fr; }} main {{ padding: 12px; }} }}
  </style>
</head>
<body><main>
  <h1>竞品分析结果 A/B 盲评</h1>
  <section class="band"><h2>Evidence Summary</h2><pre>{evidence}</pre></section>
  <div class="columns">
    <section class="band"><h2>Analysis A</h2><pre>{analysis_a}</pre></section>
    <section class="band"><h2>Analysis B</h2><pre>{analysis_b}</pre></section>
  </div>
  <section class="band"><h2>评分</h2><table><thead><tr><th>维度</th><th>A</th><th>B</th></tr></thead><tbody>
    {score_rows}
    <tr><td>hallucination (0-2)</td><td><input type="number" min="0" max="2"></td><td><input type="number" min="0" max="2"></td></tr>
    <tr><td>overall_preference</td><td colspan="2"><select><option></option><option>A</option><option>B</option><option>TIE</option></select></td></tr>
  </tbody></table></section>
</main></body></html>"""


def write_artifacts(artifact: dict) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    (RESULT_DIR / "competitor_ab_latest.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RESULT_DIR / "competitor_ab_score_template.json").write_text(
        json.dumps(score_template(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RESULT_DIR / "competitor_ab_latest.html").write_text(render_html(artifact), encoding="utf-8")


def main() -> int:
    evidence = load_evidence()
    baseline = RuleBaselineCompetitorAnalyzer().analyze(evidence)
    try:
        client = LLMClient()
    except LLMError:
        print("LLM_PROVIDER_NOT_CONFIGURED")
        return 2
    try:
        llm = LLMStructuredCompetitorAnalyzer(llm_client=client).analyze(evidence)
    except CompetitorAnalysisError as exc:
        if exc.code != "ANALYSIS_GROUNDING_FAILED":
            raise
        detail = exc.payload["message"].rsplit("：", 1)[-1]
        write_artifacts(build_failed_blind_artifact(evidence, baseline, exc.code, [detail]))
        print(json.dumps({"provider": client.provider, "model": client.model, **exc.payload}, ensure_ascii=False))
        return 3
    artifact = build_blind_artifact(evidence, baseline, llm)
    write_artifacts(artifact)
    print(
        json.dumps(
            {
                "provider": client.provider,
                "model": client.model,
                "note_count": len(evidence.used_note_ids),
                "comment_count": len(evidence.used_comment_ids),
                "baseline_grounding": grounding_summary(evidence, baseline),
                "llm_grounding": grounding_summary(evidence, llm),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
