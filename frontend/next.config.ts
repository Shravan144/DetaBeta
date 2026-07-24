import type { NextConfig } from "next";

// Browser requests always target the same-origin `/api` route.  Next.js proxies
// those requests to the backend, using localhost for a regular local checkout
// and the Compose service name when DetaBeta runs in Docker.
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
