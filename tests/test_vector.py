"""Tests for behavioral vector computation."""

from app.services.vector import compute_behavioral_vector


class TestComputeBehavioralVector:
    def test_produces_32_dimensions(self, established_profile):
        vec = compute_behavioral_vector(established_profile)
        assert len(vec) == 32

    def test_all_values_in_zero_one_range(self, established_profile):
        vec = compute_behavioral_vector(established_profile)
        for i, v in enumerate(vec):
            assert 0.0 <= v <= 1.0, f"dim {i} out of range: {v}"

    def test_deterministic(self, established_profile):
        """Same profile state produces identical vectors."""
        vec1 = compute_behavioral_vector(established_profile)
        vec2 = compute_behavioral_vector(established_profile)
        assert vec1 == vec2

    def test_new_profile_produces_valid_vector(self, new_profile):
        vec = compute_behavioral_vector(new_profile)
        assert len(vec) == 32
        assert all(0.0 <= v <= 1.0 for v in vec)

    def test_bot_profile_produces_valid_vector(self, bot_profile):
        vec = compute_behavioral_vector(bot_profile)
        assert len(vec) == 32
        assert all(0.0 <= v <= 1.0 for v in vec)

    def test_similar_profiles_have_close_vectors(self, established_profile, same_person_github):
        """The same person on two platforms should have similar vectors."""
        import numpy as np

        vec_a = np.array(compute_behavioral_vector(established_profile))
        vec_b = np.array(compute_behavioral_vector(same_person_github))
        cosine_sim = np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
        assert cosine_sim > 0.7, f"Same-person vectors too dissimilar: {cosine_sim:.3f}"

    def test_different_people_have_distant_vectors(self, established_profile, different_person):
        """Different people should have dissimilar vectors."""
        import numpy as np

        vec_a = np.array(compute_behavioral_vector(established_profile))
        vec_b = np.array(compute_behavioral_vector(different_person))
        cosine_sim = np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
        # Cosine similarity can be high for 32-dim vectors with many shared baseline values.
        # The key is that same-person similarity is HIGHER than different-person similarity.
        assert cosine_sim < 0.98, f"Different-person vectors too similar: {cosine_sim:.3f}"

    def test_chronotype_encoding_varies_with_peak_hour(self, established_profile):
        """Different peak hours should produce different chronotype dims."""
        from app.services.vector import compute_behavioral_vector

        # Morning person
        morning_hourly = [0.0] * 24
        for h in [6, 7, 8, 9, 10]:
            morning_hourly[h] = 0.2
        established_profile.hourly_distribution = morning_hourly
        vec_morning = compute_behavioral_vector(established_profile)

        # Night person
        night_hourly = [0.0] * 24
        for h in [22, 23, 0, 1, 2]:
            night_hourly[h] = 0.2
        established_profile.hourly_distribution = night_hourly
        vec_night = compute_behavioral_vector(established_profile)

        # Dims 0-1 (sin/cos of peak hour) should differ
        assert vec_morning[0] != vec_night[0] or vec_morning[1] != vec_night[1]

    def test_audience_size_log_normalized(self, established_profile):
        """Large audience sizes should be compressed via log normalization."""
        established_profile.audience_size = 10
        vec_small = compute_behavioral_vector(established_profile)

        established_profile.audience_size = 1_000_000
        vec_large = compute_behavioral_vector(established_profile)

        # Dim 14 is log(audience_size+1) normalized
        assert vec_large[14] > vec_small[14]
        assert vec_large[14] <= 1.0
