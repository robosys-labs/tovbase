"use client";

import { getScoreColor, getTier } from "@/lib/api";

interface ScoreBadgeProps {
  score: number;
  size?: number;
}

export default function ScoreBadge({ score, size = 72 }: ScoreBadgeProps) {
  const color = getScoreColor(score);
  const tier = getTier(score);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 1000) * circumference;

  return (
    <div
      className="relative flex items-center justify-center shrink-0"
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0 -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={4}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
        />
      </svg>
      <div className="flex flex-col items-center leading-none">
        <span
          className="font-bold"
          style={{ color, fontSize: size * 0.3 }}
        >
          {score}
        </span>
        <span
          className="text-gray-500 mt-0.5"
          style={{ fontSize: size * 0.13 }}
        >
          {tier}
        </span>
      </div>
    </div>
  );
}
