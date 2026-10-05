import { test, expect } from '../../../src/controlplane/ui/node_modules/@playwright/test/index.js';
import { authenticateSession } from './auth-helper.ts';

test.describe('Safe Error Inspection Modal and XSS Sanitization', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateSession(page);
  });
  test('escapes XSS input without script execution, secrets, or raw stack traces in user-visible DOM', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/');

    // Ensure baseline window has no XSS flag
    const initialFlag = await page.evaluate(() => (window as unknown as { __xss_executed?: boolean }).__xss_executed);
    expect(initialFlag).toBeFalsy();

    // Trigger test safe error modal with embedded script and img onerror tags
    const testModalBtn = page.locator('[data-testid="test-error-modal-btn"]');
    await expect(testModalBtn).toBeVisible();
    await testModalBtn.click();

    // Verify modal is displayed
    const modal = page.locator('[data-testid="safe-error-modal"]');
    await expect(modal).toBeVisible();

    // Give time for any malicious script to have executed if unescaped
    await page.waitForTimeout(500);

    // Verify window.__xss_executed was NEVER set
    const executedFlag = await page.evaluate(() => (window as unknown as { __xss_executed?: boolean }).__xss_executed);
    expect(executedFlag).toBeFalsy();

    // Verify the text is safely rendered as escaped text content, not executable HTML
    const detailBox = page.locator('[data-testid="error-modal-detail"]');
    await expect(detailBox).toContainText('<script>window.__xss_executed=true;</script>');
    await expect(detailBox).toContainText('Lỗi kiểm thử chẩn đoán an toàn!');

    // Verify technical_detail_ref is shown as opaque UUID reference
    const refBox = page.locator('[data-testid="technical-detail-ref"]');
    await expect(refBox).toBeVisible();
    const refText = await refBox.textContent();
    expect(refText?.trim()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

    // Verify retrieval of technical details renders safe metadata and notice, but NO raw stack trace in DOM
    const fetchBtn = page.locator('[data-testid="fetch-technical-detail-btn"]');
    await expect(fetchBtn).toBeVisible();
    await fetchBtn.click();

    const detailContent = page.locator('[data-testid="technical-detail-content"]');
    await expect(detailContent).toBeVisible();
    await expect(detailContent).toContainText('TestDiagnosticError');
    await expect(page.locator('[data-testid="safe-diagnostic-notice"]')).toBeVisible();

    // Verify no secret patterns or raw stack traces exist anywhere in visible DOM
    const bodyText = await page.innerText('body');
    expect(bodyText).not.toContain('CANARY_SECRET');
    expect(bodyText).not.toContain('m2test_password');
    expect(bodyText).not.toContain('POSTGRES_PASSWORD');
    expect(bodyText).not.toContain('Traceback (most recent call last)');
    expect(bodyText).not.toContain('canary_raw_stack_trace_leak');
    expect(bodyText).not.toContain('File "/app/test.py"');

    const fullHtml = await page.content();
    expect(fullHtml).not.toContain('Traceback (most recent call last)');
    expect(fullHtml).not.toContain('canary_raw_stack_trace_leak');
    expect(fullHtml).not.toContain('File "/app/test.py"');

    // Close modal
    await page.locator('[data-testid="dismiss-error-modal-btn"]').click();
    await expect(modal).not.toBeVisible();
  });
});
