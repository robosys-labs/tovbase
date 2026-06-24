"use client";

import { useState, useEffect } from "react";
import {
  searchTopics,
  type TopicSearchParams,
  type TopicSearchResponse,
  type TopicEntry,
  getScoreColor,
} from "@/lib/api";
import PlatformBadge from "@/components/PlatformBadge";

const PLATFORMS = [
  "twitter",
  "reddit",
  "hackernews",
  "linkedin",
  "github",
  "bluesky",
  "youtube",
];

const TIME_WINDOWS: { label: string; hours: number }[] = [
  { label: "Last hour", hours: 1 },
  { label: "Last 6 hours", hours: 6 },
  { label: "Last 24 hours", hours: 24 },
  { label: "Last 7 days", hours: 168 },
];

function formatRelativeTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function sentimentLabel(value: number): { text: string; color: string } {
  if (value >= 0.3) return { text: "Positive", color: "#10b981" };
  if (value <= -0.3) return { text: "Negative", color: "#ef4444" };
  return { text: "Neutral", color: "#6b7280" };
}

function TopicCard({ entry }: { entry: TopicEntry }) {
  const sentiment = sentimentLabel(entry.sentiment);
  const topCategory = Object.entries(entry.categories).sort(
    ([, a], [, b]) => b - a
  )[0];

  return (
    <div className="border border-gray-200 rounded-xl p-5 hover:border-gray-300 transition-colors flex flex-col gap-3">
      {/* Header: platform + time */}
      <div className="flex items-center justify-between gap-2">
        <PlatformBadge platform={entry.platform} />
        <span className="text-xs text-gray-400 shrink-0">
          {formatRelativeTime(entry.published_at)}
        </span>
      </div>

      {/* Title */}
      {entry.title ? (
        entry.url ? (
          <a
            href={entry.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-gray-900 hover:text-indigo-600 transition-colors line-clamp-2 leading-snug"
          >
            {entry.title}
          </a>
        ) : (
          <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 leading-snug">
            {entry.title}
          </h3>
        )
      ) : null}

      {/* Summary */}
      {entry.summary && (
        <p className="text-xs text-gray-500 line-clamp-3 leading-relaxed">
          {entry.summary}
        </p>
      )}

      {/* Source + category */}
      <div className="flex items-center gap-2 flex-wrap">
        {entry.source_name && (
          <span className="text-xs text-gray-400">{entry.source_name}</span>
        )}
        {topCategory && (
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
            {topCategory[0]}
          </span>
        )}
      </div>

      {/* Metrics row */}
      <div className="flex items-center gap-3 pt-2 border-t border-gray-100 mt-auto">
        {/* Sentiment */}
        <div className="flex items-center gap-1">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: sentiment.color }}
          />
          <span className="text-xs font-medium" style={{ color: sentiment.color }}>
            {sentiment.text}
          </span>
        </div>

        {/* Engagement */}
        <div className="flex items-center gap-1">
          <svg
            className="w-3.5 h-3.5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
            />
          </svg>
          <span className="text-xs text-gray-500">
            {entry.engagement_score.toFixed(1)}
          </span>
        </div>

        {/* Author trust score */}
        {entry.author_trust_score != null && (
          <div className="flex items-center gap-1 ml-auto">
            {entry.author_handle && (
              <span className="text-xs text-gray-400 truncate max-w-[80px]">
                @{entry.author_handle}
              </span>
            )}
            <span
              className="text-xs font-semibold"
              style={{ color: getScoreColor(entry.author_trust_score) }}
            >
              {entry.author_trust_score}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TopicsPage() {
  const [query, setQuery] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [windowHours, setWindowHours] = useState(24);
  const [categories, setCategories] = useState<string[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<TopicSearchResponse | null>(null);
  const [searched, setSearched] = useState(false);

  // Fetch available categories on mount
  useEffect(() => {
    async function fetchCategories() {
      try {
        const res = await fetch("/api/topics/categories");
        if (res.ok) {
          const data = await res.json();
          // Support both array and { categories: [...] } response shapes
          if (Array.isArray(data)) {
            setAvailableCategories(data);
          } else if (data?.categories && Array.isArray(data.categories)) {
            setAvailableCategories(data.categories);
          }
        }
      } catch {
        // Categories are optional — fail silently
      }
    }
    fetchCategories();
  }, []);

  function togglePlatform(platform: string) {
    setSelectedPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    );
  }

  async function performSearch() {
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);

    const params: TopicSearchParams = {
      query: query.trim(),
      window_hours: windowHours,
      limit: 30,
    };
    if (selectedPlatforms.length > 0) {
      params.platforms = selectedPlatforms;
    }
    const cats = selectedCategory ? [selectedCategory] : categories;
    if (cats.length > 0) {
      params.categories = cats;
    }

    const data = await searchTopics(params);
    setResults(data);
    setLoading(false);
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    performSearch();
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Topic Search</h1>
        <p className="mt-1 text-sm text-gray-500">
          Search trust-scored discussions across platforms
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="space-y-4 mb-10">
        {/* Query input + search button */}
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search topics..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="bg-gray-900 text-white font-medium text-sm rounded-lg px-6 py-2.5 hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>

        {/* Filters row */}
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Category dropdown */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
          >
            <option value="">All categories</option>
            {availableCategories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          {/* Time window */}
          <select
            value={windowHours}
            onChange={(e) => setWindowHours(Number(e.target.value))}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
          >
            {TIME_WINDOWS.map((tw) => (
              <option key={tw.hours} value={tw.hours}>
                {tw.label}
              </option>
            ))}
          </select>
        </div>

        {/* Platform chips */}
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((platform) => {
            const active = selectedPlatforms.includes(platform);
            const label =
              platform.charAt(0).toUpperCase() + platform.slice(1);
            return (
              <button
                key={platform}
                type="button"
                onClick={() => togglePlatform(platform)}
                className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
                  active
                    ? "border-gray-900 bg-gray-900 text-white"
                    : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                {label}
              </button>
            );
          })}
          {selectedPlatforms.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedPlatforms([])}
              className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1.5 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </form>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-gray-500">
            <svg
              className="animate-spin w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span className="text-sm">Searching topics...</span>
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && results && (
        <>
          {/* Result count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">
              {results.total_results} result
              {results.total_results !== 1 ? "s" : ""} for &ldquo;
              {results.query}&rdquo;
            </p>
            {results.categories_found &&
              Object.keys(results.categories_found).length > 0 && (
                <div className="flex gap-1.5 flex-wrap">
                  {Object.entries(results.categories_found)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 5)
                    .map(([cat, count]) => (
                      <span
                        key={cat}
                        className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded"
                      >
                        {cat} ({count})
                      </span>
                    ))}
                </div>
              )}
          </div>

          {/* Grid */}
          {results.results.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.results.map((entry) => (
                <TopicCard key={entry.id} entry={entry} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20">
              <p className="text-gray-400 text-sm">
                No results found. Try broadening your search or changing
                filters.
              </p>
            </div>
          )}
        </>
      )}

      {/* Empty state — before first search */}
      {!loading && !searched && (
        <div className="text-center py-20">
          <svg
            className="w-12 h-12 text-gray-300 mx-auto mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <p className="text-gray-400 text-sm">
            Search for topics to see trust-scored discussions across platforms
          </p>
        </div>
      )}

      {/* Error state — search returned null (API error) */}
      {!loading && searched && !results && (
        <div className="text-center py-20">
          <svg
            className="w-10 h-10 text-red-300 mx-auto mb-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <p className="text-gray-500 text-sm font-medium">
            Something went wrong
          </p>
          <p className="text-gray-400 text-xs mt-1">
            Could not reach the search API. Please try again.
          </p>
          <button
            type="button"
            onClick={performSearch}
            className="mt-4 inline-flex items-center gap-2 bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-gray-800 transition-colors"
          >
            Retry search
          </button>
        </div>
      )}
    </div>
  );
}
