import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  assetPrefix: "/static",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
