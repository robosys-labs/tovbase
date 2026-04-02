import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Tovbase — Due diligence in 30 seconds",
  description:
    "Instant trust scores for any online identity. Verify people, companies, and AI agents before you engage.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-white text-gray-900 min-h-screen flex flex-col">
        <header className="border-b border-gray-100">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
            <Link
              href="/"
              className="text-lg font-bold tracking-tight text-gray-900"
            >
              Tovbase
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                href="/topics"
                className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                Topics
              </Link>
              <a
                href="#extension"
                className="text-sm font-medium text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg px-3 py-1.5 transition-colors"
              >
                Install Extension
              </a>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-gray-100 py-8 mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center text-sm text-gray-400">
            Tovbase — Open trust infrastructure for the internet
          </div>
        </footer>
      </body>
    </html>
  );
}
