const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const outputDir = "/Users/vigneshsrinivasan/.gemini/antigravity/brain/c26b25e8-ebdf-4ab1-8dfc-c1d66a3193f1/screenshots";

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const pagesToCapture = [
  { name: "14_admin_av_dashboard.png", url: "http://127.0.0.1:8080/admin_AV/admin_dashboard.html" },
  { name: "15_admin_av_inbox.png", url: "http://127.0.0.1:8080/admin_AV/inbox.html" },
  { name: "16_admin_av_submit_ticket.png", url: "http://127.0.0.1:8080/admin_AV/submit-ticket.html" },
  { name: "17_admin_av_announcements.png", url: "http://127.0.0.1:8080/admin_AV/announcements.html" },
  { name: "18_admin_av_knowledge_base.png", url: "http://127.0.0.1:8080/admin_AV/knowledge-base.html" },
  { name: "19_admin_av_analytics.png", url: "http://127.0.0.1:8080/admin_AV/analytics.html" },
  { name: "20_admin_av_archive.png", url: "http://127.0.0.1:8080/admin_AV/archive.html" },
  { name: "21_admin_av_settings.png", url: "http://127.0.0.1:8080/admin_AV/settings.html" }
];

(async () => {
  console.log("Launching Chromium browser for Admin AV pages...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.5
  });

  const page = await context.newPage();

  for (const item of pagesToCapture) {
    const targetPath = path.join(outputDir, item.name);
    console.log(`Navigating to ${item.url}...`);
    await page.goto(item.url, { waitUntil: "networkidle" });
    await page.waitForTimeout(500); // ensure animations settle
    await page.screenshot({ path: targetPath, fullPage: true });
    console.log(`Captured screenshot: ${targetPath}`);
  }

  await browser.close();
  console.log("All Admin AV screenshots successfully captured!");
})();
