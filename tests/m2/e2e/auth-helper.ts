import { Page } from '@playwright/test';

export async function authenticateSession(page: Page) {
  // 1. Request a valid test launch capability
  const capRes = await page.request.post('/test-driver/issue-capability');
  if (!capRes.ok()) {
    throw new Error(`Failed to issue capability: ${capRes.status()} ${await capRes.text()}`);
  }
  const { capability } = await capRes.json();

  // 2. Call /v1/session/bootstrap with double-submit CSRF headers to set cookies
  const bootRes = await page.request.post('/v1/session/bootstrap', {
    headers: {
      'x-launch-capability': capability,
      'Origin': 'https://localhost:8000',
      'Cookie': 'csrf_token=init-csrf-token',
      'X-CSRF-Token': 'init-csrf-token',
    },
  });

  if (!bootRes.ok()) {
    throw new Error(`Failed to bootstrap session: ${bootRes.status()} ${await bootRes.text()}`);
  }
}