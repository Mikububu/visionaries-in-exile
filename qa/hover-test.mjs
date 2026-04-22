import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto("https://visionaries-in-exile.netlify.app", { waitUntil: "networkidle" });
await page.click(".enter-button");
await page.waitForTimeout(500);
// Hover over hoffmann's face position (455,94) in the 640x480 stage
const stage = await page.$(".stage");
const box = await stage.boundingBox();
const faceX = box.x + (455 + 68);  // center of hoffmann face
const faceY = box.y + (94 + 107);
await page.mouse.move(faceX, faceY);
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/hover-hoffmann.png" });
// Also screenshot a hover on neutra (365, 282)
await page.mouse.move(box.x + 365 + 120, box.y + 282 + 100);
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/hover-neutra.png" });
await browser.close();
console.log("saved hover screenshots");
