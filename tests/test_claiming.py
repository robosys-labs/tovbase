"""Tests for the profile claiming and verification endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import CanonicalIdentity, IdentityProfile, PendingClaim
from app.schemas import ClaimRequest, ClaimResponse, VerifyRequest, VerifyResponse


# ---------------------------------------------------------------------------
# Test-scoped in-memory SQLite database
# ---------------------------------------------------------------------------

_engine = create_engine("sqlite:///:memory:")
_TestSession = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


def _db():
    """Provide a test DB session."""
    session = _TestSession()
    try:
        return session
    except Exception:
        session.close()
        raise


def _seed_profile(db, handle="claimuser", platform="twitter", is_claimed=False, canonical_id=None):
    """Insert a minimal IdentityProfile (and optionally a CanonicalIdentity) for testing."""
    canonical = None
    if canonical_id is None:
        canonical = CanonicalIdentity(
            primary_handle=handle,
            primary_platform=platform,
            display_name="Claim Test User",
            trust_score=500,
        )
        db.add(canonical)
        db.flush()
        canonical_id = canonical.id

    profile = IdentityProfile(
        handle=handle,
        platform=platform,
        display_name="Claim Test User",
        is_claimed=is_claimed,
        canonical_identity_id=canonical_id,
        observation_count=10,
        account_age_days=365,
    )
    db.add(profile)
    db.commit()
    return profile, canonical or db.get(CanonicalIdentity, canonical_id)


# ---------------------------------------------------------------------------
# Helpers — call route functions directly with a test DB session
# ---------------------------------------------------------------------------


def _create_claim(db, handle="claimuser", platform="twitter", method="platform_bio"):
    from app.api.routes import create_claim as _route
    req = ClaimRequest(handle=handle, platform=platform, verification_method=method)
    return _route(req, db)


def _verify_claim(db, claim_id: str, proof: str):
    from app.api.routes import verify_claim as _route
    req = VerifyRequest(claim_id=claim_id, proof=proof)
    return _route(req, db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateClaim:
    def test_claim_returns_challenge(self):
        """POST /v1/profile/claim returns a challenge string for valid profile."""
        db = _db()
        try:
            _seed_profile(db)
            resp = _create_claim(db)

            assert isinstance(resp, ClaimResponse)
            assert resp.challenge.startswith("trustgate-verify-")
            assert len(resp.challenge) == len("trustgate-verify-") + 12
            assert resp.verification_method == "platform_bio"
            assert resp.claim_id  # non-empty UUID string
            assert resp.expires_at  # ISO timestamp
        finally:
            db.close()

    def test_claim_creates_pending_record(self):
        """The claim endpoint persists a PendingClaim row with status=pending."""
        db = _db()
        try:
            _seed_profile(db)
            resp = _create_claim(db)

            claim = db.get(PendingClaim, uuid.UUID(resp.claim_id))
            assert claim is not None
            assert claim.status == "pending"
            assert claim.handle == "claimuser"
            assert claim.platform == "twitter"
            assert claim.verification_method == "platform_bio"
        finally:
            db.close()

    def test_claim_nonexistent_profile_404(self):
        """Claiming a profile that doesn't exist returns 404."""
        from fastapi import HTTPException

        db = _db()
        try:
            with pytest.raises(HTTPException) as exc_info:
                _create_claim(db, handle="ghost", platform="twitter")
            assert exc_info.value.status_code == 404
        finally:
            db.close()

    def test_claim_already_claimed_409(self):
        """Claiming a profile that is already claimed returns 409."""
        from fastapi import HTTPException

        db = _db()
        try:
            _seed_profile(db, is_claimed=True)
            with pytest.raises(HTTPException) as exc_info:
                _create_claim(db)
            assert exc_info.value.status_code == 409
        finally:
            db.close()

    def test_claim_invalid_method_422(self):
        """An invalid verification_method returns 422."""
        from fastapi import HTTPException

        db = _db()
        try:
            _seed_profile(db)
            with pytest.raises(HTTPException) as exc_info:
                _create_claim(db, method="carrier_pigeon")
            assert exc_info.value.status_code == 422
        finally:
            db.close()


class TestVerifyClaim:
    def test_verify_correct_proof_succeeds(self):
        """Submitting proof matching the challenge marks the profile as claimed."""
        db = _db()
        try:
            _seed_profile(db)
            claim_resp = _create_claim(db)

            resp = _verify_claim(db, claim_resp.claim_id, claim_resp.challenge)

            assert isinstance(resp, VerifyResponse)
            assert resp.verified is True
            assert resp.canonical_id is not None
            assert resp.message == "Profile claimed successfully"

            # Verify DB state
            profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == "claimuser",
                    IdentityProfile.platform == "twitter",
                )
            ).scalar_one()
            assert profile.is_claimed is True

            claim = db.get(PendingClaim, uuid.UUID(claim_resp.claim_id))
            assert claim.status == "verified"
        finally:
            db.close()

    def test_verify_wrong_proof_fails(self):
        """Submitting incorrect proof returns verified=False."""
        db = _db()
        try:
            _seed_profile(db)
            claim_resp = _create_claim(db)

            resp = _verify_claim(db, claim_resp.claim_id, "wrong-proof-string")

            assert resp.verified is False
            assert resp.message == "Proof does not match challenge"

            # Profile should still NOT be claimed
            profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == "claimuser",
                    IdentityProfile.platform == "twitter",
                )
            ).scalar_one()
            assert profile.is_claimed is False
        finally:
            db.close()

    def test_verify_expired_claim_410(self):
        """A claim past its expires_at returns 410 Gone."""
        from fastapi import HTTPException

        db = _db()
        try:
            _seed_profile(db)
            claim_resp = _create_claim(db)

            # Manually expire the claim
            claim = db.get(PendingClaim, uuid.UUID(claim_resp.claim_id))
            claim.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
            db.commit()

            with pytest.raises(HTTPException) as exc_info:
                _verify_claim(db, claim_resp.claim_id, claim_resp.challenge)
            assert exc_info.value.status_code == 410

            # Claim status should be marked expired
            db.refresh(claim)
            assert claim.status == "expired"
        finally:
            db.close()

    def test_verify_nonexistent_claim_404(self):
        """Verifying a claim_id that doesn't exist returns 404."""
        from fastapi import HTTPException

        db = _db()
        try:
            fake_id = str(uuid.uuid4())
            with pytest.raises(HTTPException) as exc_info:
                _verify_claim(db, fake_id, "anything")
            assert exc_info.value.status_code == 404
        finally:
            db.close()

    def test_verify_already_verified_returns_true(self):
        """Re-verifying an already verified claim returns verified=True gracefully."""
        db = _db()
        try:
            _seed_profile(db)
            claim_resp = _create_claim(db)

            # First verification
            _verify_claim(db, claim_resp.claim_id, claim_resp.challenge)

            # Second verification — should succeed gracefully
            resp = _verify_claim(db, claim_resp.claim_id, claim_resp.challenge)
            assert resp.verified is True
            assert resp.message == "Claim was already verified"
        finally:
            db.close()
