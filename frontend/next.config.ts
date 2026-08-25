import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  skipTrailingSlashRedirect: true,
  allowedDevOrigins: ["127.0.0.1"],
  images: { formats: ["image/avif", "image/webp"], dangerouslyAllowLocalIP: false },
  async redirects() {
    return [
      {
        source: "/checkout/payment-status/:externalReference",
        destination: "/pedido/resultado?external_reference=:externalReference",
        permanent: false,
      },
    ];
  },
  async rewrites() {
    if (!process.env.API_PROXY_TARGET) return [];
    return [
      { source: "/api/v1/:path*", destination: `${process.env.API_PROXY_TARGET}/api/v1/:path*/` },
      { source: "/media/:path*", destination: `${process.env.API_PROXY_TARGET}/media/:path*` },
    ];
  },
};

export default nextConfig;
