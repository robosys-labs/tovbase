"""Tests for the trust scoring engine."""

from app.services.scoring import compute_trust_score, score_to_tier
from app.services.vector import compute_behavioral_vector


class TestScoreTier:
    def test_excellent(self):
        assert score_to_tier(900) == "excellent"
        assert score_to_tier(850) == "excellent"
        assert score_to_tier(1000) == "excellent"

    def test_good(self):
        assert score_to_tier(700) == "good"
        assert score_to_tier(849) == "good"

    def test_fair(self):
        assert score_to_tier(550) == "fair"
        assert score_to_tier(699) == "fair"

    def test_poor(self):
        assert score_to_tier(350) == "poor"
        assert score_to_tier(549) == "poor"

    def test_untrusted(self):
        assert score_to_tier(0) == "untrusted"
        assert score_to_tier(349) == "untrusted"


class TestComputeTrustScore:
    def test_empty_profiles_returns_zero(self):
        result = compute_trust_score([])
        assert result.final_score == 0
        assert result.tier == "untrusted"

    def test_established_profile_scores_well(self, established_profile):
        result = compute_trust_score([established_profile])
        assert result.final_score > 300, f"Established profile scored too low: {result.final_score}"
        # Single platform with 0.80 dampening (25 obs) — "poor" or better is expected
        assert result.tier in ("poor", "fair", "good", "excellent")
        assert result.confidence > 0.3

    def test_new_profile_heavily_dampened(self, new_profile):
        result = compute_trust_score([new_profile])
        assert result.dampening_factor < 1.0
        assert result.final_score < 200, f"New profile should be dampened: {result.final_score}"

    def test_bot_profile_scores_low(self, bot_profile):
        result = compute_trust_score([bot_profile])
        assert result.final_score < 400, f"Bot profile scored too high: {result.final_score}"
        # Engagement should be low for bot
        assert result.engagement < 60

    def test_multi_platform_boosts_score(self, established_profile, same_person_github):
        """Being on multiple platforms should increase the score."""
        single_result = compute_trust_score([established_profile])

        vecs = {
            str(established_profile.id): compute_behavioral_vector(established_profile),
            str(same_person_github.id): compute_behavioral_vector(same_person_github),
        }
        multi_result = compute_trust_score([established_profile, same_person_github], vecs)

        # Cross-platform score should be higher with 2 platforms
        assert multi_result.cross_platform > single_result.cross_platform

    def test_score_breakdown_sums_correctly(self, established_profile):
        result = compute_trust_score([established_profile])
        expected_raw = (
            result.existence + result.consistency + result.engagement + result.cross_platform + result.maturity
        )
        assert abs(result.raw_total - expected_raw) < 1.0  # float precision

    def test_score_capped_at_1000(self, established_profile):
        # Even with perfect signals, score should not exceed 1000
        established_profile.regularity_score = 1.0
        established_profile.active_weeks_ratio = 1.0
        established_profile.engagement_depth_ratio = 1.0
        established_profile.reciprocity_rate = 1.0
        established_profile.growth_organicity = 1.0
        established_profile.mention_response_rate = 1.0
        established_profile.authority_index = 1.0
        established_profile.profile_completeness = 1.0
        established_profile.is_verified = True
        established_profile.is_claimed = True
        established_profile.observation_count = 100

        result = compute_trust_score([established_profile])
        assert result.final_score <= 1000

    def test_dampening_at_threshold_boundaries(self, established_profile):
        """Verify dampening factors at observation count boundaries."""
        # 2 observations → heavy dampening
        established_profile.observation_count = 2
        r1 = compute_trust_score([established_profile])
        assert r1.dampening_factor == 0.33

        # 10 observations → moderate dampening
        established_profile.observation_count = 10
        r2 = compute_trust_score([established_profile])
        assert r2.dampening_factor == 0.55

        # 20 observations → light dampening
        established_profile.observation_count = 20
        r3 = compute_trust_score([established_profile])
        assert r3.dampening_factor == 0.80

        # 50 observations → no dampening
        established_profile.observation_count = 50
        r4 = compute_trust_score([established_profile])
        assert r4.dampening_factor == 1.0

    def test_anomalies_reduce_maturity(self, established_profile):
        """Anomalies should hurt the maturity sub-score."""
        clean = compute_trust_score([established_profile])

        established_profile.anomaly_count = 10
        dirty = compute_trust_score([established_profile])

        assert dirty.maturity < clean.maturity

    def test_details_populated(self, established_profile):
        result = compute_trust_score([established_profile])
        assert "existence" in result.details
        assert "consistency" in result.details
        assert "engagement" in result.details
        assert "cross_platform" in result.details
        assert "maturity" in result.details
