import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const pages = process.env.GITHUB_PAGES === "1";

export default defineConfig({
  plugins: [react()],
  base: pages ? "/dreadpit_analysis/" : "/",
  server: {
    host: true,
    allowedHosts: true,
  },
  preview: {
    host: true,
    allowedHosts: true,
  },
});
