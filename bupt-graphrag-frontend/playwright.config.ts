import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 90_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BUPT_E2E_URL || 'http://127.0.0.1:8000',
    ...devices['Desktop Chrome'],
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: process.env.BUPT_E2E_START_FIXTURE === '1' ? {
    command: '../.venv/bin/python -m uvicorn e2e_app:app --app-dir ../tests --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/healthz',
    reuseExistingServer: false,
    timeout: 60_000,
  } : undefined,
})
