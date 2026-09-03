const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const outputDir = "/Users/vigneshsrinivasan/.gemini/antigravity/brain/c26b25e8-ebdf-4ab1-8dfc-c1d66a3193f1/screenshots";

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const pagesToCapture = [
  { name: "01_superadmin_dashboard.png", url: "http://127.0.0.1:8080/management/index.html" },
  { name: "02_inbox_and_leave_queue.png", url: "http://127.0.0.1:8080/management/inbox.html" },
  { name: "03_onboarding_and_visas.png", url: "http://127.0.0.1:8080/management/onboarding.html" },
  { name: "04_submit_ticket.png", url: "http://127.0.0.1:8080/management/submit-ticket.html" },
  { name: "05_departments_and_rbac.png", url: "http://127.0.0.1:8080/management/departments.html" },
  { name: "06_hr_portal.png", url: "http://127.0.0.1:8080/management/hr-portal.html" },
  { name: "07_it_portal.png", url: "http://127.0.0.1:8080/management/it-portal.html" },
  { name: "08_knowledge_ingestion.png", url: "http://127.0.0.1:8080/management/knowledge-base.html" },
  { name: "09_hr_analytics.png", url: "http://127.0.0.1:8080/management/analytics.html" },
  { name: "10_system_settings.png", url: "http://127.0.0.1:8080/management/settings.html" }
];

(async () => {
  console.log("Launching Chromium browser...");
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
  console.log("All management screenshots successfully captured!");
})();
