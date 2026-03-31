import { getProfile, getTier, getTierColor } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";
import TierLabel from "@/components/TierLabel";
import PlatformBadge from "@/components/PlatformBadge";
import SignalBar from "@/components/SignalBar";
import Link from "next/link";

export default async function ProfilePage({
  params,
}: {
  params: Promise<{ handle: string }>;
}) {
  const { handle } = await params;
  const identity = await getProfile(handle);

  if (!identity) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Profile not found
        </h1>
        <p className="text-gray-500 mb-6">
          No trust data available for &ldquo;{handle}&rdquo;. Try searching for
          a different profile.
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

  const score = identity.trust_score;
  const tier = getTier(score);
  const b = identity.breakdown as Record<string, number>;

  const signals = [
    { label: "Identity consistency", score: Math.round(Number(b.cross_platform ?? 0) / 2) },
    { label: "Account longevity", score: Math.round(Number(b.existence ?? 0) / 2) },
    { label: "Community standing", score: Math.round(Number(b.engagement ?? 0) / 2) },
    { label: "Behavioral stability", score: Math.round(Number(b.consistency ?? 0) / 2) },
    { label: "Content quality", score: Math.round(Number(b.maturity ?? 0) / 2) },
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      {/* Profile Header */}
      <div className="flex flex-col items-center text-center mb-10">
        <ScoreBadge score={score} size={96} />
        <h1 className="mt-4 text-2xl font-bold text-gray-900">
          {identity.display_name || identity.primary_handle}
        </h1>
        <div className="flex items-center gap-2 mt-2">
          <TierLabel score={score} tier={tier} />
        </div>

        <div className="flex flex-wrap justify-center gap-1.5 mt-4">
          {identity.profiles.map((p) => (
            <PlatformBadge
              key={p.platform}
              platform={p.platform}
              verified={p.is_verified}
            />
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
        <StatCard
          label="Platforms"
          value={identity.profiles.length.toString()}
        />
        <StatCard label="Trust Score" value={score.toString()} />
        <StatCard label="Tier" value={tier} />
        <StatCard
          label="Confidence"
          value={`${Math.round(identity.confidence * 100)}%`}
        />
      </div>

      {/* Trust Signals */}
      <div className="border border-gray-200 rounded-xl p-6 mb-8">
        <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
          Trust Signals
        </h2>
        <div className="space-y-4">
          {signals.map((s) => (
            <SignalBar key={s.label} label={s.label} score={s.score} />
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col items-center gap-3">
        <Link
          href={`/report/${identity.primary_handle}`}
          className="inline-flex items-center gap-2 bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-gray-800 transition-colors"
        >
          View full report
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </Link>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-gray-200 rounded-lg p-3 text-center">
      <div className="text-lg font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  );
}
