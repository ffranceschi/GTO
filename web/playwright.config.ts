import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  use: { baseURL: "http://127.0.0.1:5173" },
  webServer: [
    {
      command: "cd .. && GTO_DATA_DIR=./data/e2e uv run uvicorn gto_api.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    { command: "npm run dev", url: "http://127.0.0.1:5173", reuseExistingServer: true },
  ],
});
