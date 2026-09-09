from app.crawler.providers.base import BaseCrawlerProvider
from app.crawler.providers.manual import ManualProvider
from app.crawler.providers.manual_snapshot_provider import ManualSnapshotProvider
from app.crawler.providers.mcp_xhs_provider import MCPXhsProvider
from app.crawler.providers.readonly_xhs_provider import ReadOnlyXhsProvider
from app.crawler.providers.seed_sample import SeedSampleProvider


PROVIDER_ORDER = ("readonly_xhs", "mcp_xhs", "manual_snapshot", "seed_sample")
PROVIDERS: dict[str, BaseCrawlerProvider] = {
    ReadOnlyXhsProvider.name: ReadOnlyXhsProvider(),
    MCPXhsProvider.name: MCPXhsProvider(),
    ManualSnapshotProvider.name: ManualSnapshotProvider(),
    SeedSampleProvider.name: SeedSampleProvider(),
    ManualProvider.name: ManualProvider(),
}


def get_collection_provider(provider_name: str) -> BaseCrawlerProvider:
    """根据名称获取采集 Provider。"""
    provider = PROVIDERS.get(provider_name)
    if provider:
        return provider
    raise ValueError(f"不支持的采集 Provider：{provider_name}")


def get_provider_chain(provider_name: str | None = None) -> list[BaseCrawlerProvider]:
    """按 readonly_xhs 到 seed_sample 的顺序返回 Provider 调度链。"""
    ordered_names = list(PROVIDER_ORDER)
    if provider_name and provider_name in PROVIDERS:
        ordered_names = [provider_name, *[name for name in ordered_names if name != provider_name]]
    return [PROVIDERS[name] for name in ordered_names]
