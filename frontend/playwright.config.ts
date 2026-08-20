import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure" },
  webServer: [
    { command: "node tests/mock-api.mjs", port: 4010, reuseExistingServer: true },
    {
      command: "pnpm dev",
      port: 3000,
      reuseExistingServer: true,
      env: { ...process.env, API_INTERNAL_URL: "http://127.0.0.1:4010/api/v1", API_PROXY_TARGET: "http://127.0.0.1:4010" },
    },
  ],
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
