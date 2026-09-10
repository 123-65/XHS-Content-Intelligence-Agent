from app.crawler.providers.base import BaseCrawlerProvider
from app.crawler.providers.manual import ManualProvider
from app.crawler.providers.manual_snapshot_provider import ManualSnapshotProvider
from app.crawler.providers.mcp_xhs_provider import MCPXhsProvider
from app.crawler.providers.readonly_xhs_provider import ReadOnlyXhsProvider
from app.crawler.providers.seed_sample import SeedSampleProvider


PRODUCTION_PROVIDER_ORDER = ("mcp_xhs", "readonly_xhs", "manual_snapshot")
DEMO_PROVIDER_NAMES = {"seed_sample"}
PROVIDER_ORDER = PRODUCTION_PROVIDER_ORDER
PROVIDERS: dict[str, BaseCrawlerProvider] = {
    ReadOnlyXhsProvider.name: ReadOnlyXhsProvider(),
    MCPXhsProvider.name: MCPXhsProvider(),
    ManualSnapshotProvider.name: ManualSnapshotProvider(),
    SeedSampleProvider.name: SeedSampleProvider(),
    ManualProvider.name: ManualProvider(),
}


def get_collection_provider(provider_name: str | None = None) -> BaseCrawlerProvider:
    """根据名称获取采集 Provider。"""
    provider = PROVIDERS.get(provider_name or PROVIDER_ORDER[0])
    if provider:
        return provider
    raise ValueError(f"不支持的采集 Provider：{provider_name}")


def get_provider_chain(provider_name: str | None = None) -> list[BaseCrawlerProvider]:
    """返回生产 Provider 调度链；seed_sample 仅允许显式 demo/test 使用。"""
    if provider_name in DEMO_PROVIDER_NAMES:
        return [PROVIDERS[provider_name]]
    if provider_name and provider_name not in PROVIDERS:
        raise ValueError(f"不支持的采集 Provider：{provider_name}")

    ordered_names = list(PROVIDER_ORDER)
    if provider_name:
        ordered_names = [provider_name, *[name for name in ordered_names if name != provider_name]]
    return [PROVIDERS[name] for name in ordered_names]
