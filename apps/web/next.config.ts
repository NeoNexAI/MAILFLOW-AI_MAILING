import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output keeps the Docker image small (only the server + traced deps).
  output: "standalone",
};

// next-intl will be re-introduced when the i18n request config + locale routing
// land (the dependency is already in package.json). Until then the plugin is
// disabled so `next build` does not require ./i18n/request.ts.
export default nextConfig;
