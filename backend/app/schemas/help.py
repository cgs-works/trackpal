from pydantic import BaseModel, Field


class HelpSafeNavigation(BaseModel):
    route: str
    settings_category: str | None = None


class HelpTopicSummary(BaseModel):
    id: str
    title: str
    summary: str
    module: str
    route: str
    order: int
    help_targets: list[str] = Field(default_factory=list)
    safe_navigation: HelpSafeNavigation


class HelpIndexResponse(BaseModel):
    schema_version: int
    content_version: str
    frontend_target_contract_version: str
    locale: str
    topics: list[HelpTopicSummary] = Field(default_factory=list)


class HelpTopicResponse(HelpTopicSummary):
    body: str


class HelpSearchResult(BaseModel):
    id: str
    title: str
    module: str
    route: str
    order: int
    excerpt: str


class HelpSearchResponse(BaseModel):
    query: str
    locale: str
    results: list[HelpSearchResult] = Field(default_factory=list)
