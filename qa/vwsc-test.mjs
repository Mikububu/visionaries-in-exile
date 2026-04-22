import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
page.on("pageerror", e => console.log("[err]", e.message));
await page.goto("http://localhost:5173", { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(1500);
await page.click(".enter-button");
await page.waitForTimeout(800);
// Count visible hotspots
const hotspotCount = await page.$$eval(".hotspot", els => els.length);
console.log("hotspots on page:", hotspotCount);
// Report all hotspot bounding boxes (in stage coords)
const boxes = await page.$$eval(".hotspot", els => els.map(e => ({
  aria: e.getAttribute("aria-label"),
  rect: e.getBoundingClientRect(),
})));
console.log("first 6 hotspots:", JSON.stringify(boxes.slice(0, 6), null, 1));
await page.screenshot({ path: "/tmp/vwsc-aahaupt.png" });
// Hover over the Kiesler rollover (sprite 15 at stage (252, -1) size 104x120)
const stage = await page.$(".stage");
const box = await stage.boundingBox();
await page.mouse.move(box.x + 252 + 52, box.y + 60);
await page.waitForTimeout(500);
await page.screenshot({ path: "/tmp/vwsc-hover-kiesler.png" });
// Hover over Hoffmann (ch26 at (528, 320) size 113x160)
await page.mouse.move(box.x + 528 + 56, box.y + 320 + 80);
await page.waitForTimeout(500);
await page.screenshot({ path: "/tmp/vwsc-hover-hoffmann.png" });
await browser.close();
console.log("done");
