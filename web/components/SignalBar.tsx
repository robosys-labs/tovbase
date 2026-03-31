interface SignalBarProps {
  label: string;
  score: number;
  maxScore?: number;
}

export default function SignalBar({
  label,
  score,
  maxScore = 100,
}: SignalBarProps) {
  const pct = Math.min(100, (score / maxScore) * 100);
  const color =
    score > 70 ? "#0F6E56" : score >= 50 ? "#BA7517" : "#DC2626";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-700">{label}</span>
        <span className="font-medium" style={{ color }}>
          {score}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
