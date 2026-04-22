import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", e => console.log("[pageerror]", e.message));
await page.goto("http://localhost:3127/system7", { waitUntil: "domcontentloaded", timeout: 20000 });
await page.waitForTimeout(1500);
// Click the main "Run" button
const run = await page.$('button:has-text("Run")');
if (!run) {
  console.log("no Run button; try a link");
  await page.screenshot({ path: "/tmp/mac-boot-0.png" });
  await browser.close();
  process.exit(1);
}
await run.click();
console.log("clicked Run, waiting for boot...");
// Wait for the emulator canvas to appear
await page.waitForSelector("canvas", { timeout: 30000 });
await page.waitForTimeout(12000); // give it time to boot
await page.screenshot({ path: "/tmp/mac-boot.png" });
console.log("saved boot screenshot");
await browser.close();
