import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL || "http://localhost:8001/v1";

function getTierColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case "excellent": return "#10b981";
    case "good": return "#22c55e";
    case "fair": return "#f59e0b";
    case "poor": return "#ef4444";
    default: return "#6b7280";
  }
}

function tierLabel(tier: string): string {
  if (!tier) return "Untrusted";
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ handle: string }> }
) {
  const { handle } = await params;

  let score = 0;
  let tier = "untrusted";
  let name = handle;

  try {
    const res = await fetch(`${API_BASE}/report/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: handle }),
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const data = await res.json();
      score = data.trust_score || 0;
      tier = data.tier || "untrusted";
      name = data.display_name || handle;
    }
  } catch {
    // Use defaults
  }

  const color = getTierColor(tier);
  const pct = Math.min(score / 1000, 1);
  const r = 18;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="48" viewBox="0 0 200 48">
  <rect width="200" height="48" rx="8" fill="#f9fafb" stroke="#e5e7eb" stroke-width="1"/>
  <svg x="6" y="4" width="40" height="40" viewBox="0 0 40 40">
    <circle cx="20" cy="20" r="${r}" fill="none" stroke="#e5e7eb" stroke-width="3"/>
    <circle cx="20" cy="20" r="${r}" fill="none" stroke="${color}" stroke-width="3"
      stroke-dasharray="${circ}" stroke-dashoffset="${offset}"
      stroke-linecap="round" transform="rotate(-90 20 20)"/>
    <text x="20" y="22" text-anchor="middle" dominant-baseline="central"
      font-family="system-ui,sans-serif" font-size="11" font-weight="700" fill="${color}">${score}</text>
  </svg>
  <text x="52" y="18" font-family="system-ui,sans-serif" font-size="12" font-weight="600" fill="#111827">${escapeXml(name.length > 18 ? name.slice(0, 17) + "..." : name)}</text>
  <text x="52" y="33" font-family="system-ui,sans-serif" font-size="10" fill="${color}" font-weight="600">${tierLabel(tier)}</text>
  <text x="52" y="44" font-family="system-ui,sans-serif" font-size="8" fill="#9ca3af">tovbase.com</text>
</svg>`;

  return new NextResponse(svg, {
    headers: {
      "Content-Type": "image/svg+xml",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}

function escapeXml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
