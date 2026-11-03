import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

// Outside production the CopilotKit Inspector loads its fonts and release notes from
// CopilotKit's CDN; production stays strictly same-origin.
const inspectorHosts = isProduction ? "" : " https://cdn.copilotkit.ai https://telemetry.copilotkit.ai";
const inspectorStyles = isProduction ? "" : " https://fonts.googleapis.com";
const inspectorFonts = isProduction ? "" : " https://fonts.gstatic.com";

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
  `style-src 'self' 'unsafe-inline'${inspectorStyles}`,
  "img-src 'self' data: blob:",
  `font-src 'self' data:${inspectorFonts}`,
  `connect-src 'self'${inspectorHosts}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: { rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } } },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
