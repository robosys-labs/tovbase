const PLATFORM_COLORS: Record<string, { bg: string; text: string }> = {
  linkedin: { bg: "#EFF6FF", text: "#1D4ED8" },
  twitter: { bg: "#F0F9FF", text: "#0369A1" },
  github: { bg: "#F3F4F6", text: "#1F2937" },
  reddit: { bg: "#FFF7ED", text: "#C2410C" },
  hackernews: { bg: "#FFF7ED", text: "#C2410C" },
  instagram: { bg: "#FDF2F8", text: "#BE185D" },
  bluesky: { bg: "#EFF6FF", text: "#2563EB" },
  youtube: { bg: "#FEF2F2", text: "#DC2626" },
  polymarket: { bg: "#EDE9FE", text: "#6D28D9" },
};

interface PlatformBadgeProps {
  platform: string;
  verified?: boolean;
}

export default function PlatformBadge({
  platform,
  verified,
}: PlatformBadgeProps) {
  const colors = PLATFORM_COLORS[platform.toLowerCase()] ?? {
    bg: "#F3F4F6",
    text: "#374151",
  };
  const label = platform.charAt(0).toUpperCase() + platform.slice(1);

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {label}
      {verified && (
        <svg
          className="w-3 h-3"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clipRule="evenodd"
          />
        </svg>
      )}
    </span>
  );
}
