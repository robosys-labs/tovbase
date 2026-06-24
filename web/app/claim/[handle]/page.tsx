"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  claimProfile,
  verifyProfile,
  type ClaimResponse,
  type VerifyResponse,
} from "@/lib/api";

type Platform = "twitter" | "linkedin" | "github" | "reddit" | "hackernews";
type VerificationMethod = "platform_bio" | "dns_txt" | "oauth_token";

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "twitter", label: "Twitter / X" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "github", label: "GitHub" },
  { id: "reddit", label: "Reddit" },
  { id: "hackernews", label: "Hacker News" },
];

const VERIFICATION_METHODS: { id: VerificationMethod; label: string }[] = [
  { id: "platform_bio", label: "Platform Bio" },
  { id: "dns_txt", label: "DNS TXT Record" },
  { id: "oauth_token", label: "OAuth Token" },
];

function platformLabel(id: string): string {
  return PLATFORMS.find((p) => p.id === id)?.label ?? id;
}

export default function ClaimPage() {
  const params = useParams<{ handle: string }>();
  const handle = decodeURIComponent(params.handle);

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [platform, setPlatform] = useState<Platform>("twitter");
  const [method, setMethod] = useState<VerificationMethod>("platform_bio");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 2 state
  const [claim, setClaim] = useState<ClaimResponse | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [oauthToken, setOauthToken] = useState("");

  // Step 3 state
  const [result, setResult] = useState<VerifyResponse | null>(null);

  // Countdown timer for step 2
  useEffect(() => {
    if (step !== 2 || !claim) return;

    const expiresAt = new Date(claim.expires_at).getTime();

    function tick() {
      const remaining = Math.max(
        0,
        Math.floor((expiresAt - Date.now()) / 1000)
      );
      setSecondsLeft(remaining);
    }

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [step, claim]);

  const handleStartClaim = useCallback(async () => {
    setLoading(true);
    setError(null);

    const response = await claimProfile({
      handle,
      platform,
      verification_method: method,
    });

    setLoading(false);

    if (!response) {
      setError("Failed to start claim. Please try again.");
      return;
    }

    setClaim(response);
    setStep(2);
  }, [handle, platform, method]);

  const handleVerify = useCallback(async () => {
    if (!claim) return;

    const proof =
      method === "oauth_token" ? oauthToken.trim() : claim.challenge;

    if (method === "oauth_token" && !proof) {
      setError("Please paste your OAuth token.");
      return;
    }

    setLoading(true);
    setError(null);

    const response = await verifyProfile({
      claim_id: claim.claim_id,
      proof,
    });

    setLoading(false);

    if (!response) {
      setError("Verification request failed. Please try again.");
      return;
    }

    setResult(response);
    setStep(3);
  }, [claim, method, oauthToken]);

  const handleRetry = useCallback(() => {
    setClaim(null);
    setResult(null);
    setOauthToken("");
    setError(null);
    setStep(1);
  }, []);

  function formatTime(totalSeconds: number): string {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 pt-16 pb-20">
      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
        Claim your profile: <span className="text-gray-500">@{handle}</span>
      </h1>

      {/* Step indicator */}
      <div className="mt-6 flex items-center gap-2 text-sm">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            {s > 1 && (
              <div
                className={`w-8 h-px ${step >= s ? "bg-gray-900" : "bg-gray-200"}`}
              />
            )}
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                step === s
                  ? "bg-gray-900 text-white"
                  : step > s
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-400"
              }`}
            >
              {step > s ? (
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              ) : (
                s
              )}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="mt-6 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Step 1: Platform & method selection */}
      {step === 1 && (
        <div className="mt-8 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Platform
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setPlatform(p.id)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors cursor-pointer ${
                    platform === p.id
                      ? "border-gray-900 bg-gray-900 text-white"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Verification method
            </label>
            <div className="space-y-2">
              {VERIFICATION_METHODS.map((vm) => (
                <label
                  key={vm.id}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
                    method === vm.id
                      ? "border-gray-900 bg-gray-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="verification_method"
                    value={vm.id}
                    checked={method === vm.id}
                    onChange={() => setMethod(vm.id)}
                    className="accent-gray-900"
                  />
                  <span className="text-sm font-medium text-gray-900">
                    {vm.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={handleStartClaim}
            disabled={loading}
            className="w-full bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-3 hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? "Starting claim..." : "Start Claim"}
          </button>
        </div>
      )}

      {/* Step 2: Challenge display */}
      {step === 2 && claim && (
        <div className="mt-8 space-y-6">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-2">
              Verification instructions
            </h2>

            {method === "platform_bio" && (
              <p className="text-sm text-gray-600">
                Add this text to your {platformLabel(platform)} bio:
              </p>
            )}
            {method === "dns_txt" && (
              <p className="text-sm text-gray-600">
                Add this TXT record to your domain:
              </p>
            )}
            {method === "oauth_token" && (
              <p className="text-sm text-gray-600">
                Paste your OAuth token below to verify ownership.
              </p>
            )}

            {/* Challenge string display for non-oauth methods */}
            {method !== "oauth_token" && (
              <div className="mt-3 bg-white border border-gray-200 rounded-lg px-4 py-3 font-mono text-sm text-gray-900 break-all select-all">
                {claim.challenge}
              </div>
            )}

            {/* OAuth token input */}
            {method === "oauth_token" && (
              <div className="mt-3">
                <div className="mb-2 bg-white border border-gray-200 rounded-lg px-4 py-3 font-mono text-xs text-gray-500 break-all">
                  Challenge: {claim.challenge}
                </div>
                <input
                  type="text"
                  value={oauthToken}
                  onChange={(e) => setOauthToken(e.target.value)}
                  placeholder="Paste your OAuth token here..."
                  className="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-gray-400 transition-colors"
                />
              </div>
            )}
          </div>

          {/* Timer */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Time remaining</span>
            <span
              className={`font-mono font-semibold ${secondsLeft <= 60 ? "text-red-600" : "text-gray-900"}`}
            >
              {secondsLeft > 0 ? formatTime(secondsLeft) : "Expired"}
            </span>
          </div>

          <button
            type="button"
            onClick={handleVerify}
            disabled={loading || secondsLeft === 0}
            className="w-full bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-3 hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading
              ? "Verifying..."
              : secondsLeft === 0
                ? "Challenge expired"
                : "I've done it -- Verify"}
          </button>

          <button
            type="button"
            onClick={handleRetry}
            className="w-full text-sm text-gray-500 hover:text-gray-700 transition-colors cursor-pointer"
          >
            Start over
          </button>
        </div>
      )}

      {/* Step 3: Result */}
      {step === 3 && result && (
        <div className="mt-8 space-y-6">
          {result.verified ? (
            <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-4">
                <svg
                  className="w-6 h-6 text-green-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-gray-900">
                Profile verified
              </h2>
              <p className="mt-1 text-sm text-gray-600">{result.message}</p>
              <Link
                href={`/profile/${encodeURIComponent(handle)}`}
                className="mt-4 inline-flex items-center gap-2 bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-gray-800 transition-colors"
              >
                View your profile
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </Link>
            </div>
          ) : (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <div className="mx-auto w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
                <svg
                  className="w-6 h-6 text-red-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-gray-900">
                Verification failed
              </h2>
              <p className="mt-1 text-sm text-gray-600">{result.message}</p>
              <button
                type="button"
                onClick={handleRetry}
                className="mt-4 inline-flex items-center gap-2 bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-gray-800 transition-colors cursor-pointer"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
