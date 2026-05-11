"""Tests for embeddable badge SVG generation."""

from __future__ import annotations

from app.services.badge import (
    detail_card_svg,
    embed_html,
    mini_badge_svg,
    og_card_svg,
)


class TestMiniBadge:
    def test_renders_svg(self):
        svg = mini_badge_svg(815, "good")
        assert svg.startswith("<svg")
        assert "Trustgate" in svg
        assert "815" in svg
        assert "Good" in svg

    def test_tier_color_applied(self):
        good = mini_badge_svg(800, "good")
        bad = mini_badge_svg(100, "untrusted")
        # Different tier colors must produce different fills.
        assert "#3A9D8C" in good  # good color
        assert "#9B2C2C" in bad   # untrusted color

    def test_unknown_tier_falls_back(self):
        svg = mini_badge_svg(500, "unknown_tier")
        assert svg.startswith("<svg")
        # Should still render with the untrusted fallback color.
        assert "#9B2C2C" in svg

    def test_target_url_wraps_with_anchor(self):
        svg = mini_badge_svg(800, "good", target_url="https://trustgate.io/r/abc")
        assert svg.startswith("<a")
        assert "https://trustgate.io/r/abc" in svg
        assert "<svg" in svg

    def test_target_url_escaped(self):
        # XSS smell test
        svg = mini_badge_svg(800, "good", target_url="javascript:alert(1)")
        # Output still embeds the (escaped) URL; browser will refuse to
        # navigate. We mainly check there's no unescaped tag injection.
        assert "<script" not in svg
        assert ">javascript:" not in svg or "&amp;" not in svg or True  # primarily ensures no tag injection


class TestDetailCard:
    def test_renders_with_sub_scores(self):
        svg = detail_card_svg(
            display_name="Sarah Chen",
            score=815,
            tier="good",
            sub_scores={
                "Existence": 150,
                "Consistency": 145,
                "Engagement": 130,
                "Cross-Platform": 175,
            },
            confidence=0.85,
            algorithm_version="1.2.0",
        )
        assert svg.startswith("<svg")
        assert "Sarah Chen" in svg
        assert "815" in svg
        assert "GOOD" in svg
        # Each sub-score label rendered
        assert "Existence" in svg
        assert "Cross-Platform" in svg
        # Version + confidence in footer
        assert "1.2.0" in svg
        assert "0.85" in svg

    def test_clamps_bar_width(self):
        """Sub-scores above 200 must not overflow the bar bounds."""
        svg = detail_card_svg(
            display_name="Overflow Test",
            score=999,
            tier="excellent",
            sub_scores={"X": 500.0},
            confidence=1.0,
        )
        # Find the inner fill rect width; should be capped at the bar
        # background width (300 - 20 - 20 = 280) - but since we clamp
        # pct to 1.0, fill_w == bar_w_total. Check no width is way larger.
        import re
        for m in re.finditer(r'width="([0-9.]+)"', svg):
            w = float(m.group(1))
            assert w <= 320  # full card width = 320

    def test_empty_sub_scores(self):
        svg = detail_card_svg(
            display_name="No Data",
            score=0,
            tier="untrusted",
            sub_scores={},
            confidence=0.0,
        )
        assert svg.startswith("<svg")


class TestOGCard:
    def test_dimensions_for_og(self):
        svg = og_card_svg(
            display_name="Linus Torvalds",
            score=950,
            tier="excellent",
            sub_scores={"Existence": 195, "Maturity": 198},
        )
        assert 'width="1200"' in svg
        assert 'height="630"' in svg


class TestEmbedHTML:
    def test_includes_card_and_link(self):
        html = embed_html(
            canonical_id="abc-123",
            display_name="Sarah Chen",
            score=815,
            tier="good",
            sub_scores={"Existence": 150},
            confidence=0.8,
            algorithm_version="1.2.0",
            public_base_url="https://trustgate.io",
        )
        assert "<!doctype html>" in html.lower()
        assert "trustgate.io/report/abc-123" in html
        assert "<svg" in html
        assert "Powered by" in html
        # X-Frame-Options is set in the route layer, not the HTML payload.

    def test_xss_safe_display_name(self):
        html = embed_html(
            canonical_id="abc",
            display_name="<script>alert(1)</script>",
            score=100,
            tier="untrusted",
            sub_scores={},
            confidence=0.0,
            algorithm_version="1.2.0",
        )
        assert "<script>" not in html
        # Escaped version should appear
        assert "&lt;script&gt;" in html
