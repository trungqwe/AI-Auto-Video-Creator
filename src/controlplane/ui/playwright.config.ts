import { defineConfig, devices } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const venvPythonWin = path.resolve(__dirname, '../../../.venv/Scripts/python.exe');
const pythonCmd = fs.existsSync(venvPythonWin) ? `"${venvPythonWin}"` : 'python';
const testDriverScript = path.resolve(__dirname, '../../controlplane/application/test_driver.py');

export default defineConfig({
  testDir: '../../../tests/m2/e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'https://localhost:8000',
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
  },
  webServer: {
    command: `${pythonCmd} "${testDriverScript}" serve --port 8000`,
    url: 'https://localhost:8000/test-driver/health',
    ignoreHTTPSErrors: true,
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ignoreHTTPSErrors: true,
      },
    },
  ],
});