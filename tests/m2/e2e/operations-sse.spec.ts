import { test, expect } from '../../../src/controlplane/ui/node_modules/@playwright/test/index.js';
import { authenticateSession } from './auth-helper.ts';

test.describe('Operations SSE Real-Time Stream Flow', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateSession(page);
    await page.request.post('/test-driver/set-retention-watermark', {
      data: { watermark: 0 },
    });
  });

  test.afterEach(async ({ page }) => {
    await page.request.post('/test-driver/set-retention-watermark', {
      data: { watermark: 0 },
    });
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
test('recovers from expired cursor using server-provided cursor when resync is required', async ({ page }) => {
    // 1. Open UI
    await page.goto('/');

    // 2. Wait for SSE connection badge to show connected
    const statusBadge = page.locator('[data-testid="sse-status-badge"]');
    await expect(statusBadge).toHaveClass(/connected/, { timeout: 10000 });

    // 3. Submit a batch to get an operation
    await page.locator('[data-testid="tab-command"]').click();
    const testKey = 'sse-resync-' + Date.now() + '-' + Math.random().toString(36).substring(2, 7);
    await page.locator('[data-testid="idempotency-key-input"]').fill(testKey);
    await page.locator('[data-testid="target-count-input"]').fill('2');
    await page.locator('[data-testid="submit-batch-btn"]').click();

    const receiptCard = page.locator('[data-testid="command-receipt-card"]');
    await expect(receiptCard).toBeVisible();
    const opId = (await page.locator('[data-testid="receipt-operation-id-value"]').textContent())?.trim();
    expect(opId).toBeTruthy();

    await page.locator('[data-testid="tab-operations"]').click();
    const opCell = page.locator('.ag-cell').filter({ hasText: opId! });
    await expect(opCell).toBeVisible({ timeout: 5000 });
    const row = page.locator('.ag-row', { has: opCell });
    await expect(row.locator('.pill')).toHaveText(/ACCEPTED/i);

    // 4. Advance to RUNNING to establish event and cursor
    const advanceRunning = await page.request.post('/test-driver/advance-operation', {
      data: {
        operation_id: opId,
        status: 'RUNNING',
        summary: 'Bắt đầu xử lý luồng sự kiện...',
      },
    });
    expect(advanceRunning.ok()).toBeTruthy();
    const runningCursor = (await advanceRunning.json()).cursor;

    await expect(row.locator('.pill')).toHaveText(/RUNNING/i, { timeout: 10000 });

    // 5. Set retention watermark ahead of current cursor to simulate retention expiration
    const boundaryWatermark = runningCursor + 100;
    const watermarkRes = await page.request.post('/test-driver/set-retention-watermark', {
      data: { watermark: boundaryWatermark },
    });
    expect(watermarkRes.ok()).toBeTruthy();

    // 6. Trigger reconnection via temporary offline/online cycle
    // Native EventSource reconnects with Last-Event-ID < boundaryWatermark.
    // Server returns resync_required with cursor = boundaryWatermark.
    // Client recovers by replacing lastCursor with server-provided cursor.
    await page.context().setOffline(true);
    await page.waitForTimeout(1200);
    await page.context().setOffline(false);

    // 7. Verify SSE reconnects to healthy connected state
    await expect(statusBadge).toHaveClass(/connected/, { timeout: 15000 });

    // 8. Advance operation to SUCCEEDED after recovery
    const advanceSucceeded = await page.request.post('/test-driver/advance-operation', {
      data: {
        operation_id: opId,
        status: 'SUCCEEDED',
        summary: 'Khôi phục thành công bằng cursor máy chủ cung cấp!',
      },
    });
    expect(advanceSucceeded.ok()).toBeTruthy();

    // 9. Real browser DOM updates to SUCCEEDED through the recovered stream without page reload
    await expect(row.locator('.pill')).toHaveText(/SUCCEEDED/i, { timeout: 10000 });
    await expect(row).toContainText('Khôi phục thành công bằng cursor máy chủ cung cấp!');
  });
});
