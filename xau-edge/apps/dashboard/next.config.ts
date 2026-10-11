import { execSync } from "node:child_process";
import type { NextConfig } from "next";

/** The commit this build was made from, so a served build can be compared with the source (a stale `.next` is
 * otherwise invisible). "unknown" when git is unavailable; never fails the build. */
function buildSha(): string {
  if (process.env.NEXT_PUBLIC_BUILD_SHA) return process.env.NEXT_PUBLIC_BUILD_SHA;
  try {
    return execSync("git rev-parse --short=7 HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "unknown";
  }
}

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_BUILD_SHA: buildSha() },
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
