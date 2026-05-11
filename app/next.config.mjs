/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  distDir: ".next.nosync",
  experimental: {
    serverComponentsExternalPackages: ["better-sqlite3", "pdf-parse"],
  },
};

export default nextConfig;
