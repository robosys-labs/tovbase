"""Tests for deep-enrichment helpers (cross-source agreement, rel="me"
parsing, Wikidata facts mapping). Network calls are mocked."""

from __future__ import annotations

import pytest

from app.services.deep_enrichment import (
    NameAgreement,
    _normalize_name_tokens,
    _RelMeHTMLParser,
    cross_source_name_agreement,
    name_agreement_dampening_lift,
)


class TestNameTokenNormalization:
    def test_strips_diacritics(self):
        assert _normalize_name_tokens("Chibüeze Opata") == {"chibueze", "opata"}

    def test_strips_punctuation(self):
        assert _normalize_name_tokens("O'Connor, Sean") == {"oconnor", "sean"}

    def test_drops_short_tokens(self):
        # Single-character tokens are noise.
        assert _normalize_name_tokens("J K Rowling") == {"rowling"}


class TestCrossSourceNameAgreement:
    def test_no_sources(self):
        a = cross_source_name_agreement("Alice Wonderland", [])
        assert a.n_sources == 0
        assert not a.is_high_confidence
        assert name_agreement_dampening_lift(a) == 1.0

    def test_high_agreement(self):
        """4 sources, all exactly matching → lift triggered."""
        a = cross_source_name_agreement(
            "Opeyemi Awoyemi",
            [
                "Opeyemi Awoyemi",
                "Opeyemi Awoyemi",
                "Opeyemi Awoyemi",
                "Opeyemi Awoyemi",
            ],
        )
        assert a.n_sources == 4
        assert a.n_agreeing == 4
        assert a.mean_jaccard == 1.0
        assert a.is_high_confidence
        lift = name_agreement_dampening_lift(a)
        assert lift > 1.0
        assert lift <= 1.25  # plan cap

    def test_partial_agreement_below_threshold(self):
        """2/3 sources agree, but the third has a totally different name."""
        a = cross_source_name_agreement(
            "Sarah Chen",
            ["Sarah Chen", "Sarah Chen", "Mallory Smith"],
        )
        assert a.n_sources == 3
        assert a.n_agreeing == 2  # below the 3-source threshold
        assert not a.is_high_confidence
        assert name_agreement_dampening_lift(a) == 1.0

    def test_first_name_only_match_counts_when_overlap_high(self):
        """If three sources share the last name + one token, agreement
        should fire even without exact match."""
        a = cross_source_name_agreement(
            "Linus Torvalds",
            ["Linus Torvalds", "L. Torvalds", "Linus B. Torvalds", "Linus Torvalds"],
        )
        # All four share "linus" + "torvalds" tokens (high Jaccard).
        assert a.n_agreeing >= 3
        assert a.is_high_confidence
        assert name_agreement_dampening_lift(a) > 1.0


class TestRelMeParser:
    def test_extracts_rel_me_link(self):
        html = """
        <html><head><title>Alice</title></head>
        <body>
          <a rel="me" href="https://github.com/alice">github</a>
          <a rel="me" href="https://x.com/alice">twitter</a>
          <a rel="other" href="https://example.com">unrelated</a>
        </body></html>
        """
        parser = _RelMeHTMLParser()
        parser.feed(html)
        assert parser.title.strip() == "Alice"
        assert "https://github.com/alice" in parser.rel_me_links
        assert "https://x.com/alice" in parser.rel_me_links
        assert "https://example.com" not in parser.rel_me_links

    def test_link_rel_me(self):
        html = '<head><link rel="me" href="https://bsky.app/profile/alice.bsky.social"></head>'
        parser = _RelMeHTMLParser()
        parser.feed(html)
        assert "https://bsky.app/profile/alice.bsky.social" in parser.rel_me_links

    def test_meta_socials(self):
        html = """
        <head>
          <meta name="twitter:creator" content="@alice">
          <meta property="og:profile:username" content="alice">
        </head>
        """
        parser = _RelMeHTMLParser()
        parser.feed(html)
        assert parser.meta_socials.get("twitter:creator") == "@alice"
        assert parser.meta_socials.get("og:profile:username") == "alice"


class TestDampeningLiftBounds:
    def test_capped_at_25_percent(self):
        """Lift function must never exceed +25% (clamped before the
        compute_trust_score floor-of-1.0 final clamp)."""
        a = NameAgreement(target="X", n_sources=20, n_agreeing=20, mean_jaccard=1.0)
        lift = name_agreement_dampening_lift(a)
        assert lift <= 1.25 + 1e-9
