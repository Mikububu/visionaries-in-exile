import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("console", m => console.log("[page]", m.type(), m.text().slice(0, 200)));
page.on("pageerror", e => console.log("[pageerror]", e.message));
await page.goto("http://localhost:3127", { waitUntil: "networkidle", timeout: 20000 });
await page.waitForTimeout(2000);
await page.screenshot({ path: "/tmp/imac-landing.png", fullPage: false });
const title = await page.title();
console.log("TITLE:", title);
// Look for the canvas / machine picker
const machines = await page.$$eval("a, button", els => els.map(e => e.textContent?.trim()).filter(Boolean).slice(0, 30));
console.log("BUTTONS:", machines);
await browser.close();
