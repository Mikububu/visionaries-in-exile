import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 2400 } });
const page = await ctx.newPage();
await page.goto("http://localhost:3127", { waitUntil: "networkidle", timeout: 20000 });
await page.waitForTimeout(2000);
// Get all system releases + their URLs
const systems = await page.$$eval("a, button", els => 
  els
    .map(e => ({ text: e.textContent?.trim(), href: e.href || "" }))
    .filter(x => x.text && (x.text.includes("Run") || x.text.includes("System") || x.text.includes("Mac OS") || x.text.includes("Customize")))
);
console.log("systems found:", systems.length);
// Focus on Mac OS 8/9 era
const candidates = systems.filter(s => /(System 7\.5|Mac OS 8|Mac OS 9)/.test(s.text)).slice(0, 12);
console.log("candidates:", JSON.stringify(candidates, null, 2));
// Get the page HTML for the macOS8 card
const macos8 = await page.$('text=/Mac OS 8\\.1/');
if (macos8) console.log("found mac os 8.1");
// Scroll to Mac OS 8 area
await page.keyboard.press("End");
await page.waitForTimeout(500);
await page.screenshot({ path: "/tmp/imac-fullpage.png", fullPage: true });
console.log("saved fullpage screenshot");
await browser.close();
