"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface SearchBarProps {
  large?: boolean;
}

export default function SearchBar({ large }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    // Extract a handle from various URL formats, or use as-is
    let id = trimmed;
    try {
      const url = new URL(trimmed);
      const parts = url.pathname.split("/").filter(Boolean);
      if (parts.length > 0) {
        id = parts[parts.length - 1];
      }
    } catch {
      // Not a URL, use as handle
      id = trimmed.replace(/^@/, "");
    }
    router.push(`/report/${encodeURIComponent(id)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div
        className={`flex items-center gap-2 border border-gray-200 bg-white rounded-xl shadow-sm focus-within:border-gray-400 focus-within:shadow-md transition-all ${
          large ? "p-2 pl-5" : "p-1.5 pl-4"
        }`}
      >
        <svg
          className="w-5 h-5 text-gray-400 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Paste any profile link, company URL, or agent address..."
          className={`flex-1 outline-none bg-transparent text-gray-900 placeholder:text-gray-400 ${
            large ? "text-base py-2" : "text-sm py-1.5"
          }`}
        />
        <button
          type="submit"
          className={`shrink-0 bg-gray-900 text-white font-medium rounded-lg hover:bg-gray-800 transition-colors cursor-pointer ${
            large ? "px-5 py-2.5 text-sm" : "px-4 py-2 text-sm"
          }`}
        >
          Run report
        </button>
      </div>
    </form>
  );
}
