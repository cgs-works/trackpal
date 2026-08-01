from pydantic import BaseModel, Field


class HelpSafeNavigation(BaseModel):
    route: str
    settings_category: str | None = None
    tab: str | None = None


class HelpTopicSummary(BaseModel):
    id: str
    title: str
    summary: str
    module: str
    route: str
    order: int
    help_targets: list[str] = Field(default_factory=list)
    safe_navigation: HelpSafeNavigation
    safe_links: list[HelpSafeNavigation] = Field(default_factory=list)


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


class HelpTourStep(BaseModel):
    topic_id: str
    related_topics: list[str] = Field(default_factory=list)
    title: str
    content: str
    summary: str
    route: str
    settings_category: str | None = None
    target: str
    conditional: bool = False
    order: int


class HelpTourRelease(BaseModel):
    release_id: str
    status: str | None = None
    acknowledged_at: str | None = None
    locale: str
    plan: str
    frontend_target_contract_version: str
    steps: list[HelpTourStep] = Field(default_factory=list)


class HelpTourAcknowledgementRequest(BaseModel):
    status: str = Field(pattern="^(completed|skipped)$")


class HelpTourAcknowledgementResponse(BaseModel):
    release_id: str
    status: str
    acknowledged_at: str
