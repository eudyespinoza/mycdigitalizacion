import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (!process.env.API_PROXY_TARGET) return [];
    return [{ source: "/api/v1/:path*", destination: `${process.env.API_PROXY_TARGET}/api/v1/:path*` }];
  },
};

export default nextConfig;
