import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Portal UI on :5170. Directory API defaults to docker-mapped Mel on :8101.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5170,
    strictPort: true,
    proxy: {
      "/api/directory": {
        target: process.env.VITE_DIRECTORY_PROXY_TARGET ?? "http://127.0.0.1:8101",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/directory/, ""),
      },
    },
  },
});
