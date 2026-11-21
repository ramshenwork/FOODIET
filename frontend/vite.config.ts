import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the API runs on :8000; proxying keeps everything same-origin, as in production.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000", "/q": "http://localhost:8000" } },
  build: { target: "es2020", sourcemap: false },
});
