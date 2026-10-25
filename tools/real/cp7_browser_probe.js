'use strict';
// CP7-2: mở phiên thật qua /launch bằng Playwright (nạp từ src/controlplane/ui), ghi DOM, HAR và cookie vào thư mục tạm
// ngoài cây Git, in ra JSON đã che (không bao giờ in capability, giá trị cookie hay nội dung trang).
//
//   node tools/real/cp7_browser_probe.js --url-file <tệp chứa URL /launch> --out <thư mục tạm>
//
// Kết quả trong --out: dom.html (DOM sau khi UI nạp), session.har (HAR có nội dung response), cookies.json (cookie của phiên,
// cho test dùng tiếp; tệp tạm, test xoá sau khi xong). stdout: một dòng JSON gồm trạng thái, đường dẫn cuối, tên và cờ cookie.

const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'src', 'controlplane', 'ui', 'node_modules', 'playwright'));

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

async function main() {
  const urlFile = arg('--url-file');
  const out = arg('--out');
  if (!urlFile || !out) throw new Error('usage: --url-file <file> --out <dir>');
  const url = fs.readFileSync(urlFile, 'utf8').trim();
  if (!/^https:\/\/(127\.0\.0\.1|localhost):\d+\/launch\?cap=[A-Za-z0-9_-]+$/.test(url)) throw new Error('launch URL has an unexpected shape');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: true, recordHar: { path: path.join(out, 'session.har'), content: 'embed' } });
    const page = await context.newPage();
    // UI giữ một EventSource mở suốt phiên nên mạng không bao giờ rảnh ('networkidle' không tới): chờ trang nạp, chờ React vẽ
    // tiêu đề, rồi chờ thêm một khoảng cố định để các lệnh gọi API đầu tiên kịp vào HAR.
    const response = await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    await page.waitForSelector('h1.brand-title', { timeout: 60000 });
    await page.waitForTimeout(3000);
    const finalUrl = new URL(page.url());
    fs.writeFileSync(path.join(out, 'dom.html'), await page.content(), 'utf8');
    const cookies = await context.cookies();
    fs.writeFileSync(path.join(out, 'cookies.json'), JSON.stringify(cookies), 'utf8');
    await context.close();
    process.stdout.write(`${JSON.stringify({
      ok: true,
      status: response ? response.status() : null,
      finalPath: finalUrl.pathname,
      cookies: cookies.map(c => ({ name: c.name, httpOnly: c.httpOnly, secure: c.secure, sameSite: c.sameSite, path: c.path })),
    })}\n`);
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  process.stdout.write(`${JSON.stringify({ ok: false, error: String(error && error.message || error).replace(/cap=[A-Za-z0-9_-]+/g, 'cap=[REDACTED]').slice(0, 300) })}\n`);
  process.exitCode = 1;
});
