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
  safe_links?: HelpSafeNavigation[];
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

export interface HelpTourStep {
  topic_id: string;
  related_topics: string[];
  title: string;
  content: string;
  summary: string;
  route: string;
  settings_category: string | null;
  target: string;
  conditional: boolean;
  order: number;
}

export interface HelpTourRelease {
  release_id: string;
  status: "completed" | "skipped" | null;
  acknowledged_at: string | null;
  locale: string;
  plan: "starter" | "pro";
  frontend_target_contract_version: string;
  steps: HelpTourStep[];
}

export interface HelpTourAcknowledgement {
  release_id: string;
  status: "completed" | "skipped";
  acknowledged_at: string;
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

export async function getUnseenHelpTour(): Promise<HelpTourRelease> {
  const { data } = await api.get<HelpTourRelease>("/help/tour");
  return data;
}

export async function replayHelpTour(releaseId: string): Promise<HelpTourRelease> {
  const { data } = await api.get<HelpTourRelease>(`/help/tour/${releaseId}/replay`);
  return data;
}

export async function acknowledgeHelpTour(
  releaseId: string,
  tourStatus: "completed" | "skipped",
): Promise<HelpTourAcknowledgement> {
  const { data } = await api.post<HelpTourAcknowledgement>(
    `/help/tour/${releaseId}/acknowledge`,
    { status: tourStatus },
  );
  return data;
}
