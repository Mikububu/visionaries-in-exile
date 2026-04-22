import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
await page.goto("https://visionaries-in-exile.netlify.app", { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(1500);
await page.click(".enter-button");
await page.waitForTimeout(1500);
const n = await page.$$eval(".hotspot", els => els.length);
const names = await page.$$eval(".hotspot", els => els.map(e => e.getAttribute("aria-label")));
console.log("hotspots live:", n);
console.log("names:", names);
// Hover each one and collect where it highlights
const box = await (await page.$(".stage")).boundingBox();
// Hover Kiesler
await page.mouse.move(box.x + 252 + 52, box.y + 60);
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/live-kiesler.png" });
// Hover Schindler
await page.mouse.move(box.x + 409 + 48, box.y + 292 + 90);
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/live-schindler.png" });
await browser.close();
