import { test, expect } from '@playwright/test';
import { authenticateSession } from './auth-helper.ts';

test.describe('Admin Command Idempotency (StartProductionBatch)', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateSession(page);
  });

  test('submits StartProductionBatch with Idempotency-Key and replays same receipt on duplicate submission', async ({ page }) => {
    // 1. Navigate to application root
    await page.goto('/');
    await expect(page.locator('h1')).toHaveText(/Bảng Điều Khiển Quản Trị/);

    // 2. Open Start Batch command tab
    await page.locator('[data-testid="tab-command"]').click();
    await expect(page.locator('[data-testid="start-batch-form"]')).toBeVisible();

    // 3. Fill target count and fixed Idempotency-Key
    const testKey = `idem-test-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    await page.locator('[data-testid="target-count-input"]').fill('3');
    await page.locator('[data-testid="idempotency-key-input"]').fill(testKey);

    // 4. Submit command
    await page.locator('[data-testid="submit-batch-btn"]').click();

    // 5. Verify CommandReceipt is rendered
    const receiptCard = page.locator('[data-testid="command-receipt-card"]');
    await expect(receiptCard).toBeVisible();

    const receiptIdVal = await page.locator('[data-testid="receipt-id-value"]').textContent();
    const dispositionVal = await page.locator('[data-testid="receipt-disposition-value"]').textContent();
    const operationIdVal = await page.locator('[data-testid="receipt-operation-id-value"]').textContent();
    const resourceRefVal = await page.locator('[data-testid="receipt-resource-ref-value"]').textContent();

    expect(receiptIdVal?.trim().length).toBeGreaterThan(0);
    expect(dispositionVal?.toLowerCase()).toContain('accepted');
    expect(operationIdVal?.trim()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(resourceRefVal).toContain('production_batch');

    // 6. Check that the operation is present in the Operations AG Grid
    await page.locator('[data-testid="tab-operations"]').click();
    await expect(page.locator('[data-testid="operations-panel"]').locator('.ag-root-wrapper')).toBeVisible();
    await expect(page.locator('.ag-cell').filter({ hasText: operationIdVal!.trim() })).toBeVisible({ timeout: 10000 });

    const matchingRowsFirst = await page.locator('.ag-cell').filter({ hasText: operationIdVal!.trim() }).count();
    expect(matchingRowsFirst).toBe(1);

    // 7. Re-submit the EXACT same Idempotency-Key and payload
    await page.locator('[data-testid="tab-command"]').click();
    await expect(page.locator('[data-testid="idempotency-key-input"]')).toHaveValue(testKey);
    await expect(page.locator('[data-testid="target-count-input"]')).toHaveValue('3');

    await page.locator('[data-testid="submit-batch-btn"]').click();
    await expect(receiptCard).toBeVisible();

    const replayReceiptId = await page.locator('[data-testid="receipt-id-value"]').textContent();
    const replayOperationId = await page.locator('[data-testid="receipt-operation-id-value"]').textContent();

    // Replayed receipt must match exactly
    expect(replayReceiptId?.trim()).toBe(receiptIdVal?.trim());
    expect(replayOperationId?.trim()).toBe(operationIdVal?.trim());

    // 8. Re-check operations table: still exactly 1 operation row (no duplicate side effects)
    await page.locator('[data-testid="tab-operations"]').click();
    await expect(page.locator('.ag-cell').filter({ hasText: operationIdVal!.trim() })).toBeVisible();
    const matchingRowsSecond = await page.locator('.ag-cell').filter({ hasText: operationIdVal!.trim() }).count();
    expect(matchingRowsSecond).toBe(1);

    // 9. Negative test: reusing same Idempotency-Key with DIFFERENT payload is rejected
    await page.locator('[data-testid="tab-command"]').click();
    await page.locator('[data-testid="target-count-input"]').fill('7');
    await page.locator('[data-testid="submit-batch-btn"]').click();

    // Safe error modal should display conflict code
    await expect(page.locator('[data-testid="safe-error-modal"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="safe-error-modal"]')).toContainText('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD');
    await page.locator('[data-testid="dismiss-error-modal-btn"]').click();
    await expect(page.locator('[data-testid="safe-error-modal"]')).not.toBeVisible();
  });
});