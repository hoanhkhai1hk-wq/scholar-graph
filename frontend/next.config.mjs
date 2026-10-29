/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.SG_BUILD_DIR || ".next",
  experimental: { middlewareClientMaxBodySize: 100 * 1024 * 1024 },
};

export default nextConfig;
