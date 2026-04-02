// Tovbase API client

// Server-side: call backend directly. Client-side: use Next.js rewrite proxy.
const API_BASE =
  typeof window === "undefined"
    ? (process.env.API_URL || "http://localhost:8001/v1")
    : "/api";

export type Tier = "Excellent" | "Good" | "Fair" | "Poor" | "Untrusted";

export interface PlatformProfile {
  handle: string;
  platform: string;
  display_name: string | null;
  account_age_days: number;
  audience_size: number;
  is_verified: boolean;
  observation_count: number;
  last_observed_at: string | null;
}

export interface Identity {
  canonical_id: string;
  primary_handle: string;
  primary_platform: string;
  display_name: string | null;
  trust_score: number;
  tier: string;
  confidence: number;
  breakdown: Record<string, unknown>;
  profiles: PlatformProfile[];
  profile_url: string | null;
}

export interface Observation {
  platform: string;
  handle: string;
  activity_type: string;
  description: string;
  timestamp: string;
}

export interface SimilarIdentity {
  handle: string;
  display_name: string;
  role: string;
  trust_score: number;
  avatar_initials: string;
}

export interface ReportData {
  report_id: string;
  handle: string;
  display_name: string | null;
  platform: string;
  platforms: string[];
  trust_score: number;
  tier: string;
  confidence: number;
  claimed_role: string | null;
  claimed_org: string | null;
  is_claimed: boolean;
  existence_score: number;
  consistency_score: number;
  engagement_score: number;
  cross_platform_score: number;
  maturity_score: number;
  summary: string;
  key_findings: { type: string; title: string; description: string }[];
  ai_assessment: string;
  signals: Record<string, number>;
  recent_activity: { timestamp: string; platform: string; description: string }[];
  connections: {
    name: string;
    role: string | null;
    trust_score: number;
    initials: string;
  }[];
  network_quality: string;
}

// Score tier helpers

export function getTier(
  score: number
): "Excellent" | "Good" | "Fair" | "Poor" | "Untrusted" {
  if (score >= 850) return "Excellent";
  if (score >= 700) return "Good";
  if (score >= 550) return "Fair";
  if (score >= 350) return "Poor";
  return "Untrusted";
}

export function getTierColor(tier: string): string {
  switch (tier.toLowerCase()) {
    case "excellent":
      return "#10b981";
    case "good":
      return "#22c55e";
    case "fair":
      return "#f59e0b";
    case "poor":
      return "#ef4444";
    case "untrusted":
    default:
      return "#6b7280";
  }
}

export function getScoreColor(score: number): string {
  return getTierColor(getTier(score));
}

// API functions

async function apiFetch<T>(path: string): Promise<T | null> {
  try {
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const res = await fetch(url, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function apiPost<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export interface ScoreResponse {
  handle: string;
  platform: string | null;
  trust_score: number;
  tier: string;
  confidence: number;
  breakdown: Record<string, unknown>;
  canonical_id: string | null;
  display_name: string | null;
  num_platforms: number;
  cached: boolean;
}

export async function getScore(
  platform: string,
  handle: string
): Promise<ScoreResponse | null> {
  return apiFetch<ScoreResponse>(`/score/${platform}/${handle}`);
}

export async function getIdentity(handle: string): Promise<Identity | null> {
  return apiFetch<Identity>(`/identity/${handle}`);
}

export async function findSimilar(
  platform: string,
  handle: string
): Promise<SimilarIdentity[] | null> {
  return apiFetch<SimilarIdentity[]>(`/similar/${platform}/${handle}`);
}

export async function submitObservation(data: Observation): Promise<boolean> {
  const result = await apiPost("/profile/observe", data);
  return result !== null;
}

export async function getReport(
  query: string,
  platform?: string
): Promise<ReportData | null> {
  return apiPost<ReportData>("/report/generate", { query, platform });
}

export async function getProfile(handle: string): Promise<Identity | null> {
  return getIdentity(handle);
}

// Topic search (for agent queries)

export interface TopicSearchParams {
  query: string;
  categories?: string[];
  platforms?: string[];
  countries?: string[];
  window_hours?: number;
  limit?: number;
}

export interface TopicEntry {
  id: string;
  title: string | null;
  summary: string | null;
  url: string | null;
  platform: string;
  author_handle: string | null;
  author_trust_score: number | null;
  published_at: string;
  categories: Record<string, number>;
  sentiment: number;
  engagement_score: number;
  source_name: string | null;
}

export interface TopicSearchResponse {
  query: string;
  window_hours: number;
  total_results: number;
  results: TopicEntry[];
  categories_found: Record<string, number>;
}

export async function searchTopics(
  params: TopicSearchParams
): Promise<TopicSearchResponse | null> {
  return apiPost<TopicSearchResponse>("/topics/search", params);
}

// Profile claiming

export interface ClaimResponse {
  claim_id: string;
  challenge: string;
  verification_method: string;
  expires_at: string;
}

export interface VerifyResponse {
  verified: boolean;
  canonical_id: string | null;
  message: string;
}

export async function claimProfile(data: {
  handle: string;
  platform: string;
  verification_method: "platform_bio" | "dns_txt" | "oauth_token";
}): Promise<ClaimResponse | null> {
  return apiPost<ClaimResponse>("/profile/claim", data);
}

export async function verifyProfile(data: {
  claim_id: string;
  proof: string;
}): Promise<VerifyResponse | null> {
  return apiPost<VerifyResponse>("/profile/verify", data);
}
