"""Embeddable Trustgate score badges — SVG generation for any rendering surface.

Designed for paste-anywhere distribution:
  • Mini badge   — shields.io-style 20px tall, drops into Markdown / READMEs
  • Detail card  — 320x180 SVG with tier color + sub-score bars
  • OG card      — 1200x630 for link previews on social platforms

All output is pure SVG with no external font / JS dependency. Embeds anywhere
that renders images. Linkable via the `target_url` parameter for click-through
to the canonical Trustgate report page.
"""

from __future__ import annotations

from xml.sax.saxutils import escape


# Tier → primary color. Matches the existing front-end palette in
# `web/components/TierLabel.tsx`.
TIER_COLOR: dict[str, str] = {
    "excellent": "#0F6E56",
    "good":      "#3A9D8C",
    "fair":      "#BA7517",
    "poor":      "#C75B1E",
    "untrusted": "#9B2C2C",
}
TIER_LABEL: dict[str, str] = {
    "excellent": "Excellent",
    "good":      "Good",
    "fair":      "Fair",
    "poor":      "Poor",
    "untrusted": "Untrusted",
}
LEFT_TEXT = "Trustgate"
LEFT_COLOR = "#1F2937"
TEXT_COLOR = "#FFFFFF"


def _measure(text: str, char_w: float = 7.0, pad: float = 12.0) -> float:
    """Rough text-width estimator for a 12px sans-serif label.

    Real metrics would require pillow + a bundled font. The estimator is good
    enough for shields.io-style badges where overshooting by 2-4px is fine
    (text just sits a bit more centred).
    """
    return char_w * len(text) + pad


def mini_badge_svg(score: int, tier: str, *, target_url: str | None = None) -> str:
    """Render a 20px-tall shields.io-style score badge as SVG.

    `target_url`, if provided, wraps the badge in `<a>` so clicks navigate
    to the canonical report page (works in HTML — image embeds drop the link).
    """
    tier = (tier or "untrusted").lower()
    color = TIER_COLOR.get(tier, TIER_COLOR["untrusted"])
    right_text = f"{int(score)} {TIER_LABEL.get(tier, tier.title())}"

    left_w = _measure(LEFT_TEXT)
    right_w = _measure(right_text)
    total_w = left_w + right_w
    left_mid = left_w / 2
    right_mid = left_w + right_w / 2

    inner = (
        f'<linearGradient id="b" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="0.10"/>'
        f'<stop offset="1" stop-color="#000" stop-opacity="0.10"/>'
        f'</linearGradient>'
        f'<clipPath id="r"><rect width="{total_w:.1f}" height="20" rx="3"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{left_w:.1f}" height="20" fill="{LEFT_COLOR}"/>'
        f'<rect x="{left_w:.1f}" width="{right_w:.1f}" height="20" fill="{color}"/>'
        f'<rect width="{total_w:.1f}" height="20" fill="url(#b)"/>'
        f'</g>'
        f'<g fill="{TEXT_COLOR}" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{left_mid:.1f}" y="15">{escape(LEFT_TEXT)}</text>'
        f'<text x="{right_mid:.1f}" y="15">{escape(right_text)}</text>'
        f'</g>'
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="20" '
        f'role="img" aria-label="Trustgate {right_text}">{inner}</svg>'
    )
    if target_url:
        # When the SVG is embedded directly as HTML (not via <img>), the
        # outer link gives click-through. SVG <a> uses xlink:href in 2.0
        # spec but href works in 1.1+ and all modern browsers.
        svg = (
            f'<a href="{escape(target_url)}" target="_blank" rel="noopener" '
            f'aria-label="Trustgate report">{svg}</a>'
        )
    return svg


def detail_card_svg(
    *,
    display_name: str,
    score: int,
    tier: str,
    sub_scores: dict[str, float],
    confidence: float,
    algorithm_version: str = "1.2.0",
    target_url: str | None = None,
    width: int = 320,
    height: int = 180,
) -> str:
    """A richer 320x180 SVG card with score + top sub-scores as bars.

    `sub_scores` is mapped to bars in declaration order; cap at 4 to keep
    the card legible. Each value should be in [0, 200] (the sub-score range).
    """
    tier = (tier or "untrusted").lower()
    accent = TIER_COLOR.get(tier, TIER_COLOR["untrusted"])
    label = TIER_LABEL.get(tier, tier.title())

    # Compose bars
    bars = list(sub_scores.items())[:4]
    bar_block_y = 80
    bar_h = 14
    bar_gap = 8
    bar_x = 20
    bar_w_total = width - bar_x - 20

    bar_svg = ""
    for i, (name, val) in enumerate(bars):
        y = bar_block_y + i * (bar_h + bar_gap)
        pct = max(0.0, min(1.0, float(val) / 200.0))
        fill_w = bar_w_total * pct
        bar_svg += (
            f'<rect x="{bar_x}" y="{y}" width="{bar_w_total}" height="{bar_h}" rx="3" '
            f'fill="#E5E7EB"/>'
            f'<rect x="{bar_x}" y="{y}" width="{fill_w:.1f}" height="{bar_h}" rx="3" '
            f'fill="{accent}" fill-opacity="0.85"/>'
            f'<text x="{bar_x + 6}" y="{y + bar_h - 3}" '
            f'font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="10" '
            f'fill="#1F2937">{escape(name.title())}</text>'
            f'<text x="{bar_x + bar_w_total - 4}" y="{y + bar_h - 3}" '
            f'text-anchor="end" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
            f'font-size="10" fill="#1F2937">{int(val)}/200</text>'
        )

    safe_name = escape(display_name or "—")[:34]
    inner = (
        f'<rect width="{width}" height="{height}" rx="8" fill="#FFFFFF" stroke="#E5E7EB"/>'
        f'<rect x="0" y="0" width="6" height="{height}" rx="3" fill="{accent}"/>'
        f'<text x="20" y="28" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="11" font-weight="500" fill="#6B7280" letter-spacing="0.5">TRUSTGATE</text>'
        f'<text x="20" y="52" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="16" font-weight="600" fill="#111827">{safe_name}</text>'
        f'<text x="{width - 20}" y="52" text-anchor="end" '
        f'font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="28" '
        f'font-weight="700" fill="{accent}">{int(score)}</text>'
        f'<text x="{width - 20}" y="68" text-anchor="end" '
        f'font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="11" '
        f'fill="{accent}" letter-spacing="0.5">{label.upper()}</text>'
        f'{bar_svg}'
        f'<text x="20" y="{height - 8}" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="9" fill="#9CA3AF">algo {escape(algorithm_version)} · confidence {confidence:.2f}</text>'
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Trustgate report card for {safe_name}">{inner}</svg>'
    )
    if target_url:
        svg = (
            f'<a href="{escape(target_url)}" target="_blank" rel="noopener" '
            f'aria-label="View full Trustgate report">{svg}</a>'
        )
    return svg


def og_card_svg(
    *,
    display_name: str,
    score: int,
    tier: str,
    sub_scores: dict[str, float],
    algorithm_version: str = "1.2.0",
) -> str:
    """1200x630 SVG suitable for OG-image meta-tag use. Same composition
    as detail_card_svg but scaled for social-link preview cards."""
    return detail_card_svg(
        display_name=display_name,
        score=score,
        tier=tier,
        sub_scores=sub_scores,
        confidence=0.0,
        algorithm_version=algorithm_version,
        width=1200,
        height=630,
    )


def embed_html(
    *,
    canonical_id: str,
    display_name: str,
    score: int,
    tier: str,
    sub_scores: dict[str, float],
    confidence: float,
    algorithm_version: str,
    public_base_url: str = "https://trustgate.io",
) -> str:
    """Standalone HTML page suitable for iframe-embedding the detail card.

    Renders the same SVG card with click-through to the full report,
    plus a tiny "Powered by Trustgate" footer. Safe to serve from
    `GET /v1/embed/{canonical_id}.html` and reference in <iframe src=...>.
    """
    report_url = f"{public_base_url}/report/{canonical_id}"
    card = detail_card_svg(
        display_name=display_name,
        score=score,
        tier=tier,
        sub_scores=sub_scores,
        confidence=confidence,
        algorithm_version=algorithm_version,
        target_url=report_url,
    )
    return (
        '<!doctype html>'
        '<html lang="en"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Trustgate score for {escape(display_name)}</title>'
        '<style>'
        'html,body{margin:0;padding:0;background:transparent;'
        'font-family:-apple-system,Segoe UI,Roboto,sans-serif}'
        '.tg-wrap{padding:8px;max-width:340px}'
        '.tg-footer{margin-top:6px;font-size:10px;color:#6B7280}'
        '.tg-footer a{color:#6B7280;text-decoration:none}'
        '</style>'
        '</head><body><div class="tg-wrap">'
        f'{card}'
        f'<div class="tg-footer">Powered by <a href="{escape(public_base_url)}">trustgate.io</a></div>'
        '</div></body></html>'
    )
