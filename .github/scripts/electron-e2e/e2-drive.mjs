// 云 Windows 判据 E2 起窗(track opendesign-electron-shell;探路 U2 十跑的 e2-drive 转正)——
// 用 Playwright 把**装好的** OpenDesign.exe 真跑起来、真点。
// 用法:node e2-drive.mjs <OpenDesign.exe 完整路径> <输出目录>
// 每条判读打一行 `OK  |FAIL <名字> :: <事实>`,由外层 e2e.ps1 汇总;有 FAIL 退出码 1。截图(整屏 + 页面)进输出目录。
import { _electron as electron } from "playwright";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [exe, out] = process.argv.slice(2);
if (!exe || !out) {
  console.error("用法: node e2-drive.mjs <OpenDesign.exe> <输出目录>");
  process.exit(2);
}
fs.mkdirSync(out, { recursive: true });
const installDir = path.dirname(exe);
const shotPs1 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "shot.ps1");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;

function V(name, ok, detail) {
  if (!ok) failed++;
  console.log(`${ok ? "OK  " : "FAIL"} ${name} :: ${detail}`);
}

function desktopShot(name, rect = null) {
  const args = ["-NoProfile", "-File", shotPs1, path.join(out, `${name}.png`)];
  if (rect) args.push("-Rect", `${rect.x},${rect.y},${rect.width},${rect.height}`);
  const r = spawnSync("pwsh", args, { encoding: "utf8" });
  const text = (r.stdout || "").trim();
  console.log(`  [截图] ${name}: ${text} ${(r.stderr || "").trim()}`);
  try { return JSON.parse(text.split("\n").pop()); } catch { return null; }
}

// 安装目录里的 Python(管家 + 网关 + 工作台)各有几个
function pythonsUnderInstall() {
  return procsUnderInstall().split(", ").filter((x) => /python/i.test(x)).length;
}

// 安装目录里还活着的进程(Electron 本体 + Python 管家 + 网关 + 工作台)
function procsUnderInstall() {
  const ps = `$d='${installDir.replace(/'/g, "''")}\\'; @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($d,[StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { "$($_.ProcessId) $($_.Name)" }) -join ', '`;
  const r = spawnSync("pwsh", ["-NoProfile", "-Command", ps], { encoding: "utf8" });
  return (r.stdout || "").trim();
}

async function waitNoProcs(limitMs) {
  const t0 = Date.now();
  let left = procsUnderInstall();
  while (left && Date.now() - t0 < limitMs) {
    await sleep(1000);
    left = procsUnderInstall();
  }
  return { left, ms: Date.now() - t0 };
}

// 工作台后台(ds-web)在哪个端口:偏好 8766、顺延 20 格(ds_shell.PREFERRED)。
// 🔴 只认带 ds_root 的 /api/health —— ws 端口段(8765 起)与它重叠,别的服务回个 200 不能算。
async function findBackendPort() {
  for (let p = 8766; p <= 8786; p++) {
    try {
      const r = await fetch(`http://127.0.0.1:${p}/api/health`, { signal: AbortSignal.timeout(400) });
      if (r.ok && (await r.json()).ds_root) return p;
    } catch { /* 没开 / 不是它 */ }
  }
  return null;
}

// track opendesign-instant-ui:窗口一出来就该是工作台(app://opendesign/?shell=1),后台在旁边起。
// 从启动那一刻起就轮询后台,量「窗口栏画出来」与「后台就绪」谁先谁后。
async function launchReady(tag) {
  const t0 = Date.now();
  let backendMs = null, backendPort = null, stop = false;
  const poll = (async () => {
    while (!stop && backendMs === null && Date.now() - t0 < 240000) {
      const p = await findBackendPort();
      if (p) { backendPort = p; backendMs = Date.now() - t0; } else await sleep(100);
    }
  })();
  const app = await electron.launch({ executablePath: exe, timeout: 90000 });
  const page = await app.firstWindow();
  const firstMs = Date.now() - t0;
  await page.waitForSelector("[data-ui=window-bar]", { timeout: 90000 });
  const uiMs = Date.now() - t0;
  const backendAtUi = backendMs;                       // null = 窗口栏出来时后台还没好
  const bannerAtUi = await page.isVisible("[data-ui=backend-connecting]").catch(() => false);
  const hrefAtUi = page.url();
  await page.evaluate(() => { window.__odE2Mark = 1; }).catch(() => {});
  await poll;
  stop = true;
  console.log(`  [${tag}] 第一个窗口 +${firstMs}ms,窗口栏 +${uiMs}ms,后台就绪 +${backendMs}ms(端口 ${backendPort})`);
  return { app, page, firstMs, uiMs, backendMs, backendPort, backendAtUi, bannerAtUi, hrefAtUi };
}

const winState = (app) =>
  app.evaluate(({ BrowserWindow, screen }) => {
    const w = BrowserWindow.getAllWindows()[0];
    return {
      visible: w.isVisible(), destroyed: w.isDestroyed(), max: w.isMaximized(), min: w.isMinimized(),
      bounds: w.getBounds(), work: screen.getPrimaryDisplay().workArea,
    };
  });

// ---------------------------------------------------------------- 第一轮:起窗 / 三按钮 / 托盘 / 退出
{
  const { app, page, firstMs, uiMs, backendMs, backendPort, backendAtUi, bannerAtUi, hrefAtUi } = await launchReady("第一轮");
  V("E2.window 窗口在 10 秒内出来", firstMs < 10000, `+${firstMs}ms`);
  V("E2.instant 第一个页面就是工作台(app://opendesign/?shell=1)", hrefAtUi.startsWith("app://opendesign/?shell=1"), hrefAtUi);
  V("E2.instant 🔴 窗口栏在后台就绪**之前**就画出来了(不再先挂「正在启动」)", backendAtUi === null && backendMs !== null && uiMs < backendMs,
    `窗口栏 +${uiMs}ms / 后台 +${backendMs}ms`);
  V("E2.connecting 后台没好时有「正在启动后台」横幅", bannerAtUi, `窗口栏出来那一刻 visible=${bannerAtUi}`);
  const bannerGone = await page.waitForSelector("[data-ui=backend-connecting]", { state: "hidden", timeout: 30000 }).then(() => true, () => false);
  const nav = await page.evaluate(() => ({ mark: window.__odE2Mark, navs: performance.getEntriesByType("navigation").length, href: location.href }));
  V("E2.noreload 后台就绪后横幅 30 秒内消失,整页没有重新加载", bannerGone && nav.mark === 1 && nav.navs === 1, JSON.stringify({ bannerGone, ...nav }));
  await sleep(3000);
  const stuck = await page.isVisible("text=读不到项目列表").catch(() => false);
  V("E2.noreload 项目列表没钉死在「读不到项目列表」(就绪前的请求挂着、就绪后补上)", !stuck, `stuck=${stuck}`);
  await sleep(1500);
  desktopShot("e2-01-ui");
  await page.screenshot({ path: path.join(out, "e2-01-ui.page.png") });

  const hasGrip = await page.evaluate(() => {
    const g = document.querySelector(".win-grip");
    return g ? getComputedStyle(g).display : "none-in-dom";
  });
  V("E2.grip 自绘缩放把手已隐藏(让给系统缩放边)", hasGrip === "none" || hasGrip === "none-in-dom", hasGrip);

  await page.click("[data-ui=window-max]");
  await sleep(1200);
  let s = await winState(app);
  V("E2.max 点「最大化」后窗口是最大化", s.max, JSON.stringify(s.bounds));
  const bottom = s.bounds.y + s.bounds.height, workBottom = s.work.y + s.work.height;
  V("E2.max 最大化不盖任务栏", bottom <= workBottom + 16, `窗口底 ${bottom} / 工作区底 ${workBottom}`);
  desktopShot("e2-02-max");

  await page.click("[data-ui=window-max]");
  await sleep(1000);
  s = await winState(app);
  V("E2.restore 再点一次回到普通大小", !s.max, JSON.stringify(s.bounds));

  await page.click("[data-ui=window-min]");
  await sleep(1000);
  s = await winState(app);
  V("E2.min 点「最小化」后窗口最小化", s.min, "");
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].restore());
  await sleep(1000);

  await page.click("[data-ui=window-close]");
  await sleep(1500);
  s = await winState(app);
  V("E2.close 点「关闭」= 收进托盘(隐藏、没销毁)", !s.visible && !s.destroyed, JSON.stringify({ visible: s.visible, destroyed: s.destroyed }));
  const port = backendPort;
  let healthOk = false;
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/health`);
    healthOk = r.ok;
  } catch (e) {
    healthOk = false;
  }
  V("E2.close 收进托盘后后台还活着", healthOk, `/api/health on ${port}`);
  desktopShot("e2-03-hidden");

  // 模拟业主再双击一次图标:第二份进程应当把窗口叫出来、自己退出 —— **不许再起一套管家**(表 #9:Electron 的锁先拿)。
  const pyBefore = pythonsUnderInstall();
  const pidsOf = () => new Set(procsUnderInstall().split(", ").filter((x) => /python/i.test(x)).map((x) => x.split(" ")[0]));
  const known = pidsOf();
  const second = spawn(exe, [], { detached: true, stdio: "ignore" });
  const secondGone = new Promise((r) => second.once("exit", () => r(true)));
  second.unref();
  const t0 = Date.now();
  const strays = new Set();
  do {
    // 攻题 #21:只看 2.5 秒后的进程数抓不到「先起一套管家、撞锁、再退」的瞬时峰值 ⇒ 边等边采新冒出来的 Python
    for (const p of pidsOf()) if (!known.has(p)) strays.add(p);
    await sleep(100);
    s = await winState(app);
  } while (!s.visible && Date.now() - t0 < 15000);
  V("E2.second 再双击图标把窗口叫出来", s.visible, `${Date.now() - t0}ms`);
  await sleep(500);
  const shot = desktopShot("e2-04-restored-500ms", s.bounds);
  await page.screenshot({ path: path.join(out, "e2-04-restored-500ms.page.png") });
  // 挑战 #17 / ZCode attachWindowsWindowRepaint:「托盘还原后几何正常、画面只剩底色」。
  // **只量窗口内容区**(攻题 #19):纯底色 ≈ 1~2 种;工作台界面(字、侧栏、卡片)远多于此。
  V("E2.repaint 托盘还原后 500ms 窗口里是界面、不是一片底色", !!shot && shot.samples > 100 && shot.colors >= 5, JSON.stringify(shot));
  const t1 = Date.now();
  while (Date.now() - t1 < 3000) { for (const p of pidsOf()) if (!known.has(p)) strays.add(p); await sleep(100); }
  const secondExited = await Promise.race([secondGone, sleep(10000).then(() => false)]);
  const pyAfter = pythonsUnderInstall();
  V("E2.second 第二次打开的那一份自己退了", secondExited, "");
  V("E2.second 第二次打开从头到尾没冒出新的管家/后台进程", strays.size === 0 && pyAfter === pyBefore,
    `Python 进程 ${pyBefore} → ${pyAfter};途中冒出过 ${[...strays].join(",") || "无"}`);

  // 窗口里只许停在本机工作台(m8~m11 的真机那一半):页面自己往外站跳 ⇒ 交系统浏览器,窗口不动。
  const home = page.url();
  await page.evaluate(() => { location.href = "http://127.0.0.1:9/od-e2e-nav-probe"; }).catch(() => {});
  await sleep(2000);
  // Node 的 URL 对 app:// 给 origin === "null",比 origin 恒等 ⇒ 用前缀比
  V("E2.nav 页面往外站跳,窗口仍停在工作台", page.url().startsWith("app://opendesign/") && home.startsWith("app://opendesign/"), `${home} → ${page.url()}`);
  spawnSync("pwsh", ["-NoProfile", "-Command", "Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force"]);

  // 托盘「退出」走的是同一个 quitAll;这里经 app.quit() → before-quit → quitAll。
  const before = procsUnderInstall();
  console.log(`  退出前安装目录里的进程:${before}`);
  const exited = new Promise((r) => app.process().once("exit", r));
  await app.evaluate(({ app: a }) => a.quit()).catch(() => {});
  await Promise.race([exited, sleep(30000)]);
  const { left, ms } = await waitNoProcs(30000);
  V("E2.quit 退出后安装目录里不剩任何进程", !left, left ? `还剩:${left}` : `${ms}ms 内收干净`);
}

// ---------------------------------------------------------------- 第二轮:Electron 主进程被硬杀
// 第一跑(run 35622694746)这里的 taskkill 没杀掉主进程 ⇒ 场景根本没发生,那条 FAIL 是量具坏了。
// 现在:主进程 pid 问 Electron 自己要;先确认它**真的没了**,再去看管家与后台。
{
  const { app } = await launchReady("第二轮");
  await sleep(1500);
  const pid = await app.evaluate(() => process.pid);
  console.log(`  硬杀前(主进程 ${pid}):${procsUnderInstall()}`);
  const tk = spawnSync("taskkill", ["/F", "/PID", String(pid)], { encoding: "utf8" });   // 第一跑:taskkill 必须带 /F 且杀的是主进程本人
  console.log(`  taskkill rc=${tk.status} ${(tk.stdout || "").trim()} ${(tk.stderr || "").trim()}`);
  let gone = false;
  for (let i = 0; i < 20 && !gone; i++) {
    await sleep(500);
    gone = !procsUnderInstall().split(", ").some((x) => x.startsWith(`${pid} `));
  }
  V("E2.crash 量具:主进程确实被杀掉了", gone, `pid ${pid}`);
  const { left, ms } = await waitNoProcs(30000);
  V("E2.crash 硬杀 Electron 主进程后,管家与后台 30 秒内都收掉", gone && !left, left ? `还剩:${left}` : `${ms}ms`);
  if (left) {
    spawnSync("pwsh", ["-NoProfile", "-Command", `Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '${installDir}\\*' } | % { Stop-Process -Id $_.ProcessId -Force }`]);
  }
}

console.log(`E2 结束:FAIL ${failed} 条`);
process.exit(failed ? 1 : 0);
