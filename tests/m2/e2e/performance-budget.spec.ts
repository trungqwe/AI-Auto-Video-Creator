import { test, expect } from '@playwright/test';
import { authenticateSession } from './auth-helper.ts';

test.describe('Performance Budget (QR-PERF-005 and QR-PERF-006)', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateSession(page);
  });
  test('verifies command acknowledgement <= 1s and 95% of normal actions <= 2s', async ({ page }) => {
    await page.goto('/');

    const normalActionLatencies: number[] = [];

    // Helper to measure UI action duration
    async function measureAction(name: string, action: () => Promise<void>) {
      const start = Date.now();
      await action();
      const duration = Date.now() - start;
      normalActionLatencies.push(duration);
      // QR-PERF-005: normal actions must respond <= 2000ms
      expect(duration, `Action ${name} took ${duration}ms, exceeding 2000ms budget`).toBeLessThanOrEqual(2000);
    }

    // Measure Action 1: Switch to Command Tab
    await measureAction('Switch to Command Tab', async () => {
      await page.locator('[data-testid="tab-command"]').click();
      await expect(page.locator('[data-testid="start-batch-form"]')).toBeVisible();
    });

    // Measure Action 2: Generate New Key
    await measureAction('Generate New Key', async () => {
      const prevVal = await page.locator('[data-testid="idempotency-key-input"]').inputValue();
      await page.locator('[data-testid="generate-key-btn"]').click();
      await expect(page.locator('[data-testid="idempotency-key-input"]')).not.toHaveValue(prevVal);
    });

    // Measure Action 3: Switch to Batches Tab
    await measureAction('Switch to Batches Tab', async () => {
      await page.locator('[data-testid="tab-batches"]').click();
      await expect(page.locator('[data-testid="batches-panel"]')).toBeVisible();
    });

    // Measure Action 4: Switch to Jobs Tab
    await measureAction('Switch to Jobs Tab', async () => {
      await page.locator('[data-testid="tab-jobs"]').click();
      await expect(page.locator('[data-testid="jobs-panel"]')).toBeVisible();
    });

    // Measure Action 5: Switch to Operations Tab
    await measureAction('Switch to Operations Tab', async () => {
      await page.locator('[data-testid="tab-operations"]').click();
      await expect(page.locator('[data-testid="operations-panel"]')).toBeVisible();
    });

    // Measure Action 6: Open Error Modal
    await measureAction('Open Error Modal', async () => {
      await page.locator('[data-testid="test-error-modal-btn"]').click();
      await expect(page.locator('[data-testid="safe-error-modal"]')).toBeVisible();
    });

    // Measure Action 7: Close Error Modal
    await measureAction('Close Error Modal', async () => {
      await page.locator('[data-testid="dismiss-error-modal-btn"]').click();
      await expect(page.locator('[data-testid="safe-error-modal"]')).not.toBeVisible();
    });

    // Check QR-PERF-005 distribution
    const sorted = [...normalActionLatencies].sort((a, b) => a - b);
    const p95Index = Math.ceil(sorted.length * 0.95) - 1;
    const p95Latency = sorted[Math.max(0, p95Index)];
    expect(p95Latency, `P95 latency of normal actions was ${p95Latency}ms, exceeding 2000ms`).toBeLessThanOrEqual(2000);

    // Measure QR-PERF-006: Command acknowledgement <= 1000ms
    await page.locator('[data-testid="tab-command"]').click();
    const testKey = `perf-key-${Date.now()}`;
    await page.locator('[data-testid="idempotency-key-input"]').fill(testKey);
    await page.locator('[data-testid="target-count-input"]').fill('1');

    const cmdStart = Date.now();
    await page.locator('[data-testid="submit-batch-btn"]').click();
    await expect(page.locator('[data-testid="command-receipt-card"]')).toBeVisible({ timeout: 1000 });
    const cmdDuration = Date.now() - cmdStart;

    // QR-PERF-006 check: acknowledgement <= 1000ms
    expect(cmdDuration, `Command acknowledgement took ${cmdDuration}ms, exceeding 1000ms budget`).toBeLessThanOrEqual(1000);
  });
});