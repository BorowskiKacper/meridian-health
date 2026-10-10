import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    const origin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/backend-api/:path*", destination: `${origin}/:path*` }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // The atlas source and its three.js live beside this app, linked in by scripts/link-atlas.mjs.
    root: path.join(__dirname, ".."),
    resolveAlias: {
      "@authorod/svitylo-3d-anatomy-atlas/core": "./vendor/atlas/src/core/index.ts",
      three: "./vendor/three/build/three.module.js",
    },
    rules: {
      "*.ts": {
        condition: { path: /3d-anatomy-atlas[\\/]packages[\\/]atlas[\\/]src[\\/]/ },
        loaders: [path.join(__dirname, "scripts/atlas-ts-loader.cjs")],
        as: "*.ts",
      },
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
