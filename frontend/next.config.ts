import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the control room is client-rendered and fed by the backend's SSE stream,
  // so it ships as plain files to Azure Static Web Apps (no Node server needed).
  output: "export",
};

export default nextConfig;
