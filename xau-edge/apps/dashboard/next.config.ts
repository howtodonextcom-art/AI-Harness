import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* sandbox / e2e can set NEXT_DIST_DIR so a build never overwrites the LIVE .next */
  distDir: process.env.NEXT_DIST_DIR || ".next",
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
