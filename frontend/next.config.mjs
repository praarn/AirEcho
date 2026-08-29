/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Server-side proxy target for /api and /uploads. In docker compose this is
    // the backend service DNS name (`http://backend:8000`); the browser-facing
    // NEXT_PUBLIC_API_BASE_URL stays localhost for the WebSocket, which connects
    // straight from the browser.
    const api =
      process.env.API_PROXY_TARGET ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${api}/:path*` },
      { source: "/uploads/:path*", destination: `${api}/uploads/:path*` },
    ];
  },
};
export default nextConfig;
