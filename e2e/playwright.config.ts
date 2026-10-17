import { defineConfig } from '@playwright/test'

const webPort = process.env.REWIND_TEST_WEB_PORT ?? '3123'
const apiPort = process.env.REWIND_TEST_API_PORT ?? '8123'
const baseURL = `http://127.0.0.1:${webPort}`

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    browserName: 'chromium',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'uv run --project ../backend python ../scripts/browser_servers.py',
    url: `${baseURL}/api/health`,
    timeout: 120_000,
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
    stdout: 'ignore',
    stderr: 'pipe',
    env: {
      REWIND_API_PORT: apiPort,
      REWIND_WEB_PORT: webPort,
      REWIND_ANALYSIS_MODE: 'mock',
      REWIND_SEED_DEMO: 'true',
    },
  },
  reporter: [['list'], ['html', { open: 'never' }]],
})
