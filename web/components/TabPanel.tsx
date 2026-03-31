"use client";

import { useState } from "react";

interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
}

interface TabPanelProps {
  tabs: Tab[];
  defaultTab?: string;
}

export default function TabPanel({ tabs, defaultTab }: TabPanelProps) {
  const [active, setActive] = useState(defaultTab ?? tabs[0]?.id ?? "");

  const current = tabs.find((t) => t.id === active);

  return (
    <div>
      <div className="border-b border-gray-200">
        <nav className="flex gap-0 -mb-px" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={active === tab.id}
              onClick={() => setActive(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
                active === tab.id
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="pt-6">{current?.content}</div>
    </div>
  );
}
