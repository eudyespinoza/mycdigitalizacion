import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/production",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3001" },
  webServer: [
    { command: "node tests/mock-api.mjs", port: 4010, reuseExistingServer: false },
    {
      command: "pnpm build && node .next/standalone/frontend/server.js",
      port: 3001,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        ...process.env,
        PORT: "3001",
        API_INTERNAL_URL: "http://127.0.0.1:4010/api/v1",
        API_PROXY_TARGET: "http://127.0.0.1:4010",
      },
    },
  ],
});
