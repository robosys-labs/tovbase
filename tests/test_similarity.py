"""Tests for cross-platform identity similarity."""

from app.services.similarity import (
    chronotype_similarity,
    compute_identity_similarity,
    name_similarity,
    topic_similarity,
    vector_similarity,
    voice_similarity,
)
from app.services.vector import compute_behavioral_vector


class TestVectorSimilarity:
    def test_identical_vectors(self):
        vec = [0.5] * 32
        assert abs(vector_similarity(vec, vec) - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0] + [0.0] * 30
        b = [0.0, 1.0] + [0.0] * 30
        assert vector_similarity(a, b) < 0.01

    def test_zero_vector(self):
        assert vector_similarity([0.0] * 32, [0.5] * 32) == 0.0


class TestChronotypeSimilarity:
    def test_identical_chronotypes(self, established_profile, same_person_github):
        # Same hourly distribution and timezone
        sim = chronotype_similarity(established_profile, same_person_github)
        assert sim > 0.8, f"Identical chronotypes should be very similar: {sim:.3f}"

    def test_opposite_chronotypes(self, established_profile, different_person):
        # Day person vs night person
        sim = chronotype_similarity(established_profile, different_person)
        assert sim < 0.5, f"Opposite chronotypes should be dissimilar: {sim:.3f}"

    def test_missing_distribution(self, established_profile):
        established_profile.hourly_distribution = None
        sim = chronotype_similarity(established_profile, established_profile)
        assert sim == 0.0


class TestVoiceSimilarity:
    def test_similar_voices(self, established_profile, same_person_github):
        sim = voice_similarity(established_profile, same_person_github)
        assert sim > 0.8, f"Same person's voice should be similar: {sim:.3f}"

    def test_different_voices(self, established_profile, different_person):
        sim = voice_similarity(established_profile, different_person)
        assert sim < 0.95, f"Different people should have different voices: {sim:.3f}"


class TestNameSimilarity:
    def test_exact_match(self, established_profile, same_person_github):
        # Both have handle="testuser" and display_name="Test User"
        sim = name_similarity(established_profile, same_person_github)
        assert sim == 1.0

    def test_no_match(self, established_profile, different_person):
        sim = name_similarity(established_profile, different_person)
        assert sim < 0.5


class TestTopicSimilarity:
    def test_overlapping_topics(self, established_profile, same_person_github):
        sim = topic_similarity(established_profile, same_person_github)
        assert sim > 0.5, f"Overlapping topics should be similar: {sim:.3f}"

    def test_disjoint_topics(self, established_profile, different_person):
        sim = topic_similarity(established_profile, different_person)
        assert sim < 0.2, f"Disjoint topics should be dissimilar: {sim:.3f}"

    def test_empty_fingerprint(self, established_profile):
        established_profile.keyword_fingerprint = {}
        sim = topic_similarity(established_profile, established_profile)
        assert sim == 0.0


class TestComputeIdentitySimilarity:
    def test_same_person_high_similarity(self, established_profile, same_person_github):
        vec_a = compute_behavioral_vector(established_profile)
        vec_b = compute_behavioral_vector(same_person_github)
        result = compute_identity_similarity(established_profile, same_person_github, vec_a, vec_b)

        assert result.overall_score > 0.55, f"Same person should score high: {result.overall_score:.3f}"
        assert result.decision in ("auto_link", "review")

    def test_different_people_low_similarity(self, established_profile, different_person):
        vec_a = compute_behavioral_vector(established_profile)
        vec_b = compute_behavioral_vector(different_person)
        result = compute_identity_similarity(established_profile, different_person, vec_a, vec_b)

        assert result.overall_score < 0.75, f"Different people should score lower: {result.overall_score:.3f}"

    def test_result_has_all_components(self, established_profile, same_person_github):
        vec_a = compute_behavioral_vector(established_profile)
        vec_b = compute_behavioral_vector(same_person_github)
        result = compute_identity_similarity(established_profile, same_person_github, vec_a, vec_b)

        assert hasattr(result, "vector_similarity")
        assert hasattr(result, "chronotype_similarity")
        assert hasattr(result, "voice_similarity")
        assert hasattr(result, "name_similarity")
        assert hasattr(result, "topic_similarity")
        assert hasattr(result, "overall_score")
        assert hasattr(result, "decision")

    def test_without_vectors(self, established_profile, same_person_github):
        """Should still work without pre-computed vectors (vector component = 0)."""
        result = compute_identity_similarity(established_profile, same_person_github)
        assert result.vector_similarity == 0.0
        assert result.overall_score >= 0.0

    def test_decision_thresholds(self, established_profile, same_person_github, different_person):
        vec_a = compute_behavioral_vector(established_profile)
        vec_same = compute_behavioral_vector(same_person_github)
        vec_diff = compute_behavioral_vector(different_person)

        same_result = compute_identity_similarity(established_profile, same_person_github, vec_a, vec_same)
        diff_result = compute_identity_similarity(established_profile, different_person, vec_a, vec_diff)

        assert same_result.decision in ("auto_link", "review")
        # Different person should either be "review" or "separate"
        assert diff_result.overall_score < same_result.overall_score
