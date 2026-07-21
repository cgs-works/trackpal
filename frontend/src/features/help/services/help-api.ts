import api from "@/lib/api";

export interface HelpSafeNavigation {
  route: string;
  settings_category: string | null;
}

export interface HelpTopicSummary {
  id: string;
  title: string;
  summary: string;
  module: string;
  route: string;
  order: number;
  help_targets: string[];
  safe_navigation: HelpSafeNavigation;
}

export interface HelpIndexResponse {
  schema_version: number;
  content_version: string;
  frontend_target_contract_version: string;
  locale: string;
  topics: HelpTopicSummary[];
}

export interface HelpTopic extends HelpTopicSummary {
  body: string;
}

export interface HelpSearchResult {
  id: string;
  title: string;
  module: string;
  route: string;
  order: number;
  excerpt: string;
}

export interface HelpSearchResponse {
  query: string;
  locale: string;
  results: HelpSearchResult[];
}

export async function getHelpIndex(): Promise<HelpIndexResponse> {
  const { data } = await api.get<HelpIndexResponse>("/help");
  return data;
}

export async function getHelpTopic(topicId: string): Promise<HelpTopic> {
  const { data } = await api.get<HelpTopic>(`/help/topics/${topicId}`);
  return data;
}

export async function searchHelp(query: string): Promise<HelpSearchResponse> {
  const { data } = await api.get<HelpSearchResponse>("/help/search", {
    params: { q: query },
  });
  return data;
}
