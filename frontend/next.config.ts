import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the control room is client-rendered and fed by the backend's SSE stream,
  // so it ships as plain files to Azure Static Web Apps (no Node server needed).
  output: "export",
  // Every page as a folder with an index.html (/match/m_l1_1/index.html), so any static host
  // serves it without rewrite rules.
  trailingSlash: true,
};

export default nextConfig;
