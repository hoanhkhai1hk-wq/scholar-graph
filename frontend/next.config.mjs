/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.SG_BUILD_DIR || ".next",
};

export default nextConfig;
