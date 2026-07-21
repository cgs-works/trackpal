from pydantic import BaseModel, Field


class HelpTopicSummary(BaseModel):
    id: str
    title: str
    summary: str
    module: str
    route: str


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
    excerpt: str


class HelpSearchResponse(BaseModel):
    query: str
    locale: str
    results: list[HelpSearchResult] = Field(default_factory=list)
