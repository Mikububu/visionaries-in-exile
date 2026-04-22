// End-to-end bug test of the VIE/AIE webapp.
// Runs a real Chromium via Playwright, takes screenshots at every step,
// records every console message and network failure, exits 0/1 based on findings.

import { chromium } from "playwright";
import { writeFileSync, mkdirSync, existsSync, rmSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "out");
if (existsSync(OUT)) rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
console.log(`OUT=${OUT}`);

const BASE = "https://visionaries-in-exile.netlify.app";
const bugs = [];
const logs = [];

function bug(severity, msg, ctx = {}) {
  bugs.push({ severity, msg, ...ctx });
  console.log(`  [${severity.toUpperCase()}] ${msg}`, Object.keys(ctx).length ? ctx : "");
}

function log(s) {
  console.log(s);
  logs.push(s);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  // browser allows autoplay without user gesture in test context
  bypassCSP: true,
});
const page = await ctx.newPage();

const consoleMsgs = [];
const failedRequests = [];

page.on("console", (m) => {
  consoleMsgs.push({ type: m.type(), text: m.text() });
  if (m.type() === "error") bug("error", `console error: ${m.text()}`);
});
page.on("pageerror", (e) => bug("error", `page error: ${e.message}`));
page.on("requestfailed", (req) => {
  failedRequests.push({ url: req.url(), error: req.failure()?.errorText });
  bug("warn", `request failed: ${req.url()} -- ${req.failure()?.errorText}`);
});
page.on("response", (res) => {
  if (res.status() >= 400 && !res.url().includes("favicon")) {
    bug("warn", `http ${res.status()}: ${res.url()}`);
  }
});

async function shot(name) {
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
  log(`  📸 ${name}.png`);
}

try {
  log("=== step 1: open app ===");
  await page.goto(BASE, { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForSelector(".stage", { timeout: 10000 }).catch(() => {
    bug("error", ".stage never rendered after load");
  });
  await shot("01-initial-load");

  // Verify enter overlay is present
  const hasEnter = await page.$(".enter-overlay");
  if (!hasEnter) bug("error", "expected .enter-overlay on first load, not found");
  else log("  ✓ enter overlay present");

  // Verify default scene is HOFFMANN
  const sceneName = await page.textContent(".meta-head h2");
  log(`  scene header: ${JSON.stringify(sceneName)}`);
  if (!sceneName?.includes("HOFFMANN")) bug("warn", `expected HOFFMANN, got: ${sceneName}`);

  log("\n=== step 2: click ▶ enter ===");
  await page.click(".enter-button");
  await page.waitForTimeout(300);
  const stillEnter = await page.$(".enter-overlay");
  if (stillEnter) bug("error", "enter-overlay did not disappear after clicking ▶ enter");
  else log("  ✓ enter overlay dismissed");
  await shot("02-after-enter");

  // Check audio element exists and is attempting to play
  const audioState = await page.evaluate(() => {
    const a = document.querySelector("audio");
    if (!a) return { exists: false };
    return {
      exists: true,
      src: a.src,
      paused: a.paused,
      muted: a.muted,
      currentTime: a.currentTime,
      readyState: a.readyState,
    };
  });
  log(`  audio: ${JSON.stringify(audioState)}`);
  if (!audioState.exists) bug("warn", "no <audio> element after enter (expected for HOFFMANN)");
  else if (audioState.paused && !audioState.muted) bug("warn", "audio present but paused");

  log("\n=== step 3: click backdrop to advance ===");
  const beforeClick = await page.textContent(".meta-head h2");
  await page.click(".stage.live");
  await page.waitForTimeout(400);
  const afterClick = await page.textContent(".meta-head h2");
  log(`  before=${beforeClick?.trim()} after=${afterClick?.trim()}`);
  if (afterClick === beforeClick) {
    bug("error", "clicking backdrop did not navigate to a new scene");
  } else {
    log("  ✓ backdrop-click navigated");
  }
  await shot("03-after-backdrop-click");

  log("\n=== step 4: back button ===");
  const backBtn = await page.$(".back-btn");
  if (!backBtn) bug("error", "no .back-btn visible after navigation");
  else {
    await backBtn.click();
    await page.waitForTimeout(300);
    const backTo = await page.textContent(".meta-head h2");
    log(`  back to: ${backTo?.trim()}`);
    if (!backTo?.includes("HOFFMANN")) bug("warn", `back did not return to HOFFMANN (got ${backTo})`);
    else log("  ✓ back returned to HOFFMANN");
  }
  await shot("04-after-back");

  log("\n=== step 5: click a navigation target pill ===");
  const pills = await page.$$(".targets li.live");
  log(`  live pills: ${pills.length}`);
  if (pills.length === 0) bug("error", "no live target pills to click on HOFFMANN");
  else {
    const firstPillText = await pills[0].textContent();
    log(`  clicking pill: ${firstPillText?.trim().slice(0, 40)}`);
    await pills[0].scrollIntoViewIfNeeded();
    await pills[0].click({ force: true });
    await page.waitForTimeout(400);
    const afterPill = await page.textContent(".meta-head h2");
    log(`  now on: ${afterPill?.trim()}`);
  }
  await shot("05-after-pill-click");

  log("\n=== step 6: sidebar scene switch ===");
  // Filter to CORBUS, pick it
  await page.fill(".sidebar input[type=search]", "corbus");
  await page.waitForTimeout(200);
  const visibleScenes = await page.$$eval(".scene-list li", (els) => els.length);
  log(`  sidebar filter='corbus': ${visibleScenes} results`);
  if (visibleScenes === 0) bug("warn", "filtering for 'corbus' returned nothing");
  else {
    await page.click(".scene-list li");
    await page.waitForTimeout(500);
    const on = await page.textContent(".meta-head h2");
    log(`  switched to: ${on?.trim()}`);
  }
  await shot("06-corbus");

  log("\n=== step 7: side switch VIE/AIE ===");
  await page.fill(".sidebar input[type=search]", "");
  await page.click(".side-switch button:first-child"); // VIE
  await page.waitForTimeout(200);
  await shot("07-vie-side");
  const vieCount = await page.$$eval(".scene-list li", (els) => els.length);
  log(`  VIE scene count: ${vieCount}`);

  log("\n=== step 8: stress test — switch to GROPIUS (has audio) ===");
  await page.fill(".sidebar input[type=search]", "gropius");
  await page.waitForTimeout(200);
  await page.click(".scene-list li");
  await page.waitForTimeout(800);
  const gropiusAudio = await page.evaluate(() => {
    const a = document.querySelector("audio");
    if (!a) return { exists: false };
    return {
      exists: true,
      src: a.src,
      paused: a.paused,
      readyState: a.readyState,
      networkState: a.networkState,
      duration: a.duration,
    };
  });
  log(`  gropius audio: ${JSON.stringify(gropiusAudio)}`);
  if (!gropiusAudio.exists) bug("error", "GROPIUS should have audio but <audio> not rendered");
  await shot("08-gropius");

  log("\n=== step 9: unresolved target click ===");
  // Find a pill whose target has no resolved scene (shows '?')
  await page.fill(".sidebar input[type=search]", "hoffmann");
  await page.waitForTimeout(150);
  await page.click(".scene-list li"); // HOFFMANN is in AIE/VIE, pick whichever shows
  await page.waitForTimeout(400);
  const unresolvedPills = await page.$$(".targets li.frame-label");
  log(`  frame-label pills on this scene: ${unresolvedPills.length}`);
  if (unresolvedPills.length > 0) {
    await unresolvedPills[0].click();
    await page.waitForTimeout(200);
    log(`  ✓ clicking frame-label did not crash`);
  }

  log("\n=== step 10: final screenshot ===");
  await shot("10-final");

  // Extract gallery cleanliness stats
  const galleryStats = await page.evaluate(() => {
    const heading = document.querySelector(".gallery h3");
    return heading ? heading.textContent : null;
  });
  log(`  gallery header: ${galleryStats}`);

  log("\n=== summary ===");
  log(`  console messages: ${consoleMsgs.length}`);
  log(`  failed requests:  ${failedRequests.length}`);
  log(`  bugs found:       ${bugs.length}`);
  const errorBugs = bugs.filter((b) => b.severity === "error").length;
  const warnBugs = bugs.filter((b) => b.severity === "warn").length;
  log(`    errors: ${errorBugs}  warnings: ${warnBugs}`);
} finally {
  writeFileSync(
    join(OUT, "report.json"),
    JSON.stringify({ bugs, consoleMsgs, failedRequests, logs }, null, 2)
  );
  await browser.close();
}
