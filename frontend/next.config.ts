import type { NextConfig } from "next";

// Browser requests always target the same-origin `/api` route.  Next.js proxies
// those requests to the backend, using localhost for a regular local checkout
// and the Compose service name when DetaBeta runs in Docker.
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  experimental: {
    // Keep the same bound as FastAPI so a valid 25 MiB CSV reaches the API.
    proxyClientMaxBodySize: "25mb",
  },
  async rewrites() {
    return [
      {
        // Proxy /api/* to FastAPI backend EXCEPT /api/auth/* which is handled by NextAuth & token route.
        source: "/api/:path((?!auth).*)" as string,
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
