import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${process.env.API_URL || "http://localhost:8001/v1"}/:path*` },
    ];
  },
};

export default nextConfig;
