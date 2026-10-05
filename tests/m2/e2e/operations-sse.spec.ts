import { test, expect } from '../../../src/controlplane/ui/node_modules/@playwright/test/index.js';
import { authenticateSession } from './auth-helper.ts';

test.describe('Operations SSE Real-Time Stream Flow', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateSession(page);
  });
  test('updates the real browser DOM through ACCEPTED to RUNNING to SUCCEEDED without page refresh', async ({ page }) => {
    // 1. Open UI
    await page.goto('/');

    // 2. Wait for SSE connection badge to show connected
    const statusBadge = page.locator('[data-testid="sse-status-badge"]');
    await expect(statusBadge).toHaveClass(/connected/, { timeout: 10000 });
    await expect(statusBadge).toContainText('Đã kết nối');

    // 3. Submit a new batch command to produce a real operation
    await page.locator('[data-testid="tab-command"]').click();
    const testKey = `sse-test-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    await page.locator('[data-testid="idempotency-key-input"]').fill(testKey);
    await page.locator('[data-testid="target-count-input"]').fill('2');
    await page.locator('[data-testid="submit-batch-btn"]').click();

    // 4. Extract operation_id from CommandReceipt
    const receiptCard = page.locator('[data-testid="command-receipt-card"]');
    await expect(receiptCard).toBeVisible();
    const opId = (await page.locator('[data-testid="receipt-operation-id-value"]').textContent())?.trim();
    expect(opId).toBeTruthy();

    // 5. Switch to Operations grid
    await page.locator('[data-testid="tab-operations"]').click();
    const opCell = page.locator('.ag-cell').filter({ hasText: opId! });
    await expect(opCell).toBeVisible({ timeout: 5000 });

    // Initial state in AG Grid is ACCEPTED
    const row = page.locator('.ag-row', { has: opCell });
    await expect(row.locator('.pill')).toHaveText(/ACCEPTED/i);

    // 6. Test driver advances state to RUNNING via application port
    const advanceRunning = await page.request.post('/test-driver/advance-operation', {
      data: {
        operation_id: opId,
        status: 'RUNNING',
        summary: 'Đang tiến hành tổng hợp kịch bản...',
      },
    });
    expect(advanceRunning.ok()).toBeTruthy();

    // 7. Verify real browser DOM updates to RUNNING via SSE without page refresh
    await expect(row.locator('.pill')).toHaveText(/RUNNING/i, { timeout: 10000 });
    await expect(row).toContainText('Đang tiến hành tổng hợp kịch bản...');

    // 8. Test driver advances state to SUCCEEDED via application port
    const advanceSucceeded = await page.request.post('/test-driver/advance-operation', {
      data: {
        operation_id: opId,
        status: 'SUCCEEDED',
        summary: 'Tác vụ đã hoàn thành xuất sắc!',
      },
    });
    expect(advanceSucceeded.ok()).toBeTruthy();

    // 9. Verify real browser DOM updates to SUCCEEDED via SSE without page refresh
    await expect(row.locator('.pill')).toHaveText(/SUCCEEDED/i, { timeout: 10000 });
    await expect(row).toContainText('Tác vụ đã hoàn thành xuất sắc!');

    // 10. Verify page refresh preserves authoritative state (does not regress to ACCEPTED)
    await page.reload();
    const opCellAfterReload = page.locator('.ag-cell').filter({ hasText: opId! });
    await expect(opCellAfterReload).toBeVisible({ timeout: 5000 });
    const rowAfterReload = page.locator('.ag-row', { has: opCellAfterReload });
    await expect(rowAfterReload.locator('.pill')).toHaveText(/SUCCEEDED/i);
  });
});