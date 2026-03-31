import { getTier, getTierColor } from "@/lib/api";

interface TierLabelProps {
  score: number;
  tier?: string;
}

export default function TierLabel({ score, tier }: TierLabelProps) {
  const resolved = tier ?? getTier(score);
  const color = getTierColor(resolved);

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{
        color,
        backgroundColor: `${color}14`,
        border: `1px solid ${color}30`,
      }}
    >
      {resolved}
    </span>
  );
}
