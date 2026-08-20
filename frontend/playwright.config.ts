import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure" },
  webServer: [
    { command: "node tests/mock-api.mjs", port: 4010, reuseExistingServer: false },
    {
      command: "pnpm dev",
      port: 3000,
      reuseExistingServer: false,
      env: { ...process.env, API_INTERNAL_URL: "http://127.0.0.1:4010/api/v1", API_PROXY_TARGET: "http://127.0.0.1:4010" },
    },
  ],
  projects: [
    { name: "360", use: { viewport: { width: 360, height: 800 } } },
    { name: "768", use: { viewport: { width: 768, height: 900 } } },
    { name: "1024", use: { viewport: { width: 1024, height: 900 } } },
    { name: "1440", use: { viewport: { width: 1440, height: 1000 } } },
  ],
});
