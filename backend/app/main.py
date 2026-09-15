from app.core.config import settings
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.account_rout import router as account_router
from app.api.xhs_note_rout import router as xhs_note_router
from app.api.competitor_analysis_rout import router as competitor_analysis_router
from app.api.content_experiment_rout import router as content_experiment_router
from app.api.content_draft_rout import router as content_draft_router
from app.api.review_report_rout import router as review_report_router
from app.api.llm import router as llm_router
from app.api.keyword_seed_rout import router as keyword_seed_router
from app.api.crawler_collection_rout import router as crawler_collection_router
from app.api.competitor_rout import router as competitor_router
from app.api.competitor_report_rout import router as competitor_report_router
from app.api.content_experiment_v2_rout import router as content_experiment_v2_router
from app.api.content_draft_v2_rout import router as content_draft_v2_router
from app.api.confirmation_rout import router as confirmation_router
from app.api.context_rout import router as context_router
from app.api.optimization_rout import router as optimization_router
from app.api.post_publish_review_rout import router as post_publish_review_router
from app.api.private_conversion_rout import router as private_conversion_router
from app.api.published_note_rout import router as published_note_router
from app.api.agent_run_rout import router as agent_run_router
from app.api.provider_health_rout import router as provider_health_router
from app.api.demo_rout import router as demo_router
from app.api.developer_rout import router as developer_router
from app.api.agent_chat import router as agent_chat_router
from app.api.agent_conversation import router as agent_conversation_router
from app.api.data_source_config import router as data_source_config_router
from app.api.data_refresh_run import router as data_refresh_run_router
from app.api.evidence_refresh_run import router as evidence_refresh_run_router
from app.api.operation_run import router as operation_run_router
from app.api.operation_experiment import router as operation_experiment_router
from app.api.draft_context_preview import router as draft_context_preview_router

def create_app():
    """创建 FastAPI 应用实例。"""
    app=FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(router=health_router)
    app.include_router(account_router)
    app.include_router(account_router, prefix="/api")
    app.include_router(xhs_note_router)
    app.include_router(competitor_analysis_router)
    app.include_router(content_experiment_router)
    app.include_router(content_draft_router)
    app.include_router(review_report_router)
    app.include_router(llm_router)
    app.include_router(keyword_seed_router)
    app.include_router(crawler_collection_router)
    app.include_router(competitor_router)
    app.include_router(competitor_report_router)
    app.include_router(content_experiment_v2_router)
    app.include_router(content_draft_v2_router)
    app.include_router(confirmation_router)
    app.include_router(published_note_router)
    app.include_router(private_conversion_router)
    app.include_router(post_publish_review_router)
    app.include_router(optimization_router)
    app.include_router(agent_run_router)
    app.include_router(provider_health_router)
    app.include_router(demo_router)
    app.include_router(context_router)
    app.include_router(developer_router)
    app.include_router(agent_chat_router)
    app.include_router(agent_conversation_router)
    app.include_router(data_source_config_router)
    app.include_router(data_refresh_run_router)
    app.include_router(evidence_refresh_run_router)
    app.include_router(operation_run_router)
    app.include_router(operation_experiment_router)
    app.include_router(draft_context_preview_router)
    return app

app=create_app()
