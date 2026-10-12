/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
  },
  test: { environment: "jsdom", globals: true, include: ["tests/unit/**/*.test.{ts,tsx}"] },
});
