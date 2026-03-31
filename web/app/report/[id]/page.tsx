import { getReport, getTier, getTierColor, type ReportData } from "@/lib/api";
import type { Metadata } from "next";
import ScoreBadge from "@/components/ScoreBadge";
import TierLabel from "@/components/TierLabel";
import PlatformBadge from "@/components/PlatformBadge";
import SignalBar from "@/components/SignalBar";
import TabPanel from "@/components/TabPanel";
import ShareButton from "./share";
import Link from "next/link";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const data = await getReport(id);
  if (!data) {
    return { title: "Profile not found — Tovbase" };
  }
  const name = data.display_name || data.handle;
  const tier = getTier(data.trust_score);
  const desc = data.summary
    ? data.summary.substring(0, 155)
    : `${name} has a ${data.trust_score}/1000 trust score (${tier}) across ${data.platforms.length} platform(s).`;

  return {
    title: `${name} — ${data.trust_score}/1000 Trust Score | Tovbase`,
    description: desc,
    openGraph: {
      title: `${name} — ${data.trust_score}/1000 Trust Score`,
      description: desc,
      url: `https://tovbase.com/report/${encodeURIComponent(id)}`,
      siteName: "Tovbase",
      type: "profile",
      images: [
        {
          url: `https://tovbase.com/badge/${encodeURIComponent(data.handle)}`,
          width: 200,
          height: 48,
          alt: `${name} trust score badge`,
        },
      ],
    },
    twitter: {
      card: "summary",
      title: `${name} — ${data.trust_score}/1000 Trust Score`,
      description: desc,
    },
  };
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function AISummaryTab({ data }: { data: ReportData }) {
  return (
    <div className="space-y-6">
      <p className="text-gray-700 leading-relaxed">{data.summary}</p>

      <div>
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
          Key Findings
        </h3>
        <div className="space-y-2">
          {data.key_findings.map((f, i) => (
            <div key={i} className="flex items-start gap-2">
              {f.type === "positive" ? (
                <svg
                  className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5 text-amber-500 shrink-0 mt-0.5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
              <div>
                <span className="text-sm font-medium text-gray-900">
                  {f.title}
                </span>{" "}
                <span className="text-sm text-gray-600">{f.description}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-2">
          Assessment
        </h3>
        <p className="text-sm text-gray-700 leading-relaxed">
          {data.ai_assessment}
        </p>
      </div>
    </div>
  );
}

function TrustSignalsTab({ data }: { data: ReportData }) {
  const signals = Object.entries(data.signals).map(([key, value]) => ({
    label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    score: value,
  }));

  return (
    <div className="space-y-4">
      {signals.map((s) => (
        <SignalBar key={s.label} label={s.label} score={s.score} />
      ))}
    </div>
  );
}

function TimelineTab({ data }: { data: ReportData }) {
  if (!data.recent_activity || data.recent_activity.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-8">
        No recent activity recorded yet. Activity will appear as the profile is
        observed over time.
      </p>
    );
  }
  return (
    <div className="space-y-0">
      {data.recent_activity.map((entry, i) => (
        <div
          key={i}
          className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0"
        >
          <span className="text-xs text-gray-400 w-16 shrink-0 pt-0.5">
            {formatTime(entry.timestamp)}
          </span>
          <PlatformBadge platform={entry.platform} />
          <span className="text-sm text-gray-700">{entry.description}</span>
        </div>
      ))}
    </div>
  );
}

function NetworkTab({ data }: { data: ReportData }) {
  if (!data.connections || data.connections.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-8">
        No network connections mapped yet. Connections appear as cross-platform
        interactions are observed.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {data.connections.map((conn, i) => {
        const color = getTierColor(getTier(conn.trust_score));
        return (
          <div key={i} className="flex items-center gap-3 py-2">
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
              style={{ backgroundColor: color }}
            >
              {conn.initials}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {conn.name}
              </div>
              {conn.role && (
                <div className="text-xs text-gray-500 truncate">
                  {conn.role}
                </div>
              )}
            </div>
            <div className="text-sm font-semibold" style={{ color }}>
              {conn.trust_score}
            </div>
          </div>
        );
      })}
      {data.network_quality && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-sm text-gray-500">{data.network_quality}</p>
        </div>
      )}
    </div>
  );
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await getReport(id);

  if (!data) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Profile not found
        </h1>
        <p className="text-gray-500 mb-6">
          No trust data available for &ldquo;{id}&rdquo;. Try searching for a
          different profile.
        </p>
        <Link
          href="/"
          className="text-sm font-medium text-indigo-600 hover:underline"
        >
          Back to search
        </Link>
      </div>
    );
  }

  const tier = getTier(data.trust_score);

  const tabs = [
    {
      id: "summary",
      label: "AI Summary",
      content: <AISummaryTab data={data} />,
    },
    {
      id: "signals",
      label: "Trust Signals",
      content: <TrustSignalsTab data={data} />,
    },
    {
      id: "timeline",
      label: "Activity Timeline",
      content: <TimelineTab data={data} />,
    },
    {
      id: "network",
      label: "Network",
      content: <NetworkTab data={data} />,
    },
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      {/* Header Card */}
      <div className="border border-gray-200 rounded-xl p-6 mb-8">
        <div className="flex items-start gap-5">
          <ScoreBadge score={data.trust_score} size={72} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-gray-900">
                {data.display_name || data.handle}
              </h1>
              <TierLabel score={data.trust_score} tier={tier} />
            </div>
            {data.claimed_role && (
              <p className="text-sm text-gray-500 mt-0.5">
                {data.claimed_role}
                {data.claimed_org ? ` at ${data.claimed_org}` : ""}
              </p>
            )}
            <div className="flex flex-wrap gap-1.5 mt-3">
              {data.platforms.map((p) => (
                <PlatformBadge key={p} platform={p} />
              ))}
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2 mt-5 pt-4 border-t border-gray-100">
          <ShareButton
            handle={data.handle}
            displayName={data.display_name}
            score={data.trust_score}
            tier={tier}
          />
          <a
            href={`/badge/${encodeURIComponent(data.handle)}`}
            target="_blank"
            rel="noopener"
            className="text-sm font-medium text-gray-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors inline-flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            Embed badge
          </a>
          {!data.is_claimed && (
            <Link
              href={`/profile/${data.handle}`}
              className="ml-auto text-sm font-medium text-indigo-600 hover:underline"
            >
              Claim this profile
            </Link>
          )}
        </div>
      </div>

      {/* Tabs */}
      <TabPanel tabs={tabs} defaultTab="summary" />
    </div>
  );
}
