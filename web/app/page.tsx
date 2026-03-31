import SearchBar from "@/components/SearchBar";
import Link from "next/link";

export default function HomePage() {
  return (
    <div>
      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-24 pb-20 flex flex-col items-center text-center">
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-gray-900 max-w-xl">
          Due diligence in 30&nbsp;seconds.
        </h1>
        <p className="mt-4 text-lg text-gray-500 max-w-md">
          Instant trust scores for any online identity. No sign-up required.
        </p>
        <div className="mt-8 w-full flex justify-center">
          <SearchBar large />
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Try: linkedin.com/in/sarahchen-dev, @sarahchen_dev, or any profile URL
        </p>
      </section>

      {/* Extension CTA */}
      <section className="bg-gray-50 border-y border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-16 flex flex-col sm:flex-row items-center gap-8">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900">
              Get trust scores everywhere you browse.
            </h2>
            <p className="mt-2 text-gray-500">
              The Tovbase extension surfaces trust signals directly on
              LinkedIn, Twitter, GitHub, and more. See scores before you connect.
            </p>
            <a
              href="#extension"
              id="extension"
              className="mt-4 inline-flex items-center gap-2 bg-gray-900 text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-gray-800 transition-colors"
            >
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
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Add to Chrome — Free
            </a>
          </div>
          <div className="w-64 h-40 bg-gray-200 rounded-xl flex items-center justify-center text-gray-400 text-sm shrink-0">
            Extension preview
          </div>
        </div>
      </section>

      {/* Claim CTA */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-16 flex flex-col items-center text-center">
        <h2 className="text-2xl font-bold text-gray-900">
          Your trust score already exists.
        </h2>
        <p className="mt-2 text-gray-500 max-w-md">
          Claim your profile to take control of your digital reputation,
          get a shareable trust badge, and unlock verified status.
        </p>
        <div className="mt-6 w-full max-w-md">
          <SearchBar />
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Paste your LinkedIn, Twitter, or GitHub profile URL
        </p>
      </section>
    </div>
  );
}
