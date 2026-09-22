// 云 Windows 判据 E4 前半段(track opendesign-electron-shell)—— 替业主走一遍「重启以更新」之前的那一段:
//   ① 更新源不通(他常先开软件后开 VPN)⇒ 更新一栏说「没查到」、**不说「已是最新」**,旁边有「重试」;
//   ② 源通了,点「重试」⇒ 后台下好 ⇒ **收起的**「设置」那一行上出现「重启以更新」(挑战 a5:按钮不许只藏在弹层里);
//   ③ 点它 ⇒ 主进程先收管家、再交安装器(之后的向导由 click-wizard.ps1 点,时间线由 e2e.ps1 量)。
// 用法:node e4-drive.mjs <OpenDesign.exe> <输出目录> <更新源目录> <端口> <替身服务器日志>
// 替身服务器由这里在 ① 之后才起(pid 写进 <输出目录>/e4-serve.pid,e2e.ps1 收尾时收掉)。
// 每条判读一行 `OK  |FAIL <名字> :: <事实>`;有 FAIL 退出码 1。
import { _electron as electron } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [exe, out, updDir, port, serveLog] = process.argv.slice(2);
if (!exe || !out || !updDir || !port || !serveLog) {
  console.error("用法: node e4-drive.mjs <OpenDesign.exe> <输出目录> <更新源目录> <端口> <替身服务器日志>");
  process.exit(2);
}
const here = path.dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
function V(name, ok, detail) {
  if (!ok) failed++;
  console.log(`${ok ? "OK  " : "FAIL"} ${name} :: ${detail}`);
}

async function textOf(page, sel) {
  const el = await page.$(sel);
  return el ? (await el.innerText()).trim() : null;
}

async function waitText(page, sel, re, limitMs) {
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < limitMs) {
    last = await textOf(page, sel).catch(() => null);
    if (last && re.test(last)) return { ok: true, text: last, ms: Date.now() - t0 };
    await sleep(1000);
  }
  return { ok: false, text: last, ms: Date.now() - t0 };
}

const app = await electron.launch({ executablePath: exe, timeout: 90000 });
const page = await app.firstWindow();
await page.waitForURL(/shell=1/, { timeout: 240000 });
await page.waitForSelector("[data-ui=window-bar]", { timeout: 90000 });

// ① 源不通。首查延迟 ≤ 60s(m16),失败后要说人话。
await page.click("[data-ui=settings-toggle]");
const offline = await waitText(page, "[data-ui=update-status]", /没查到|查不到|失败/, 150000);
V("E4.offline 源不通时更新一栏说没查到", offline.ok, `「${offline.text}」 +${offline.ms}ms`);
V("E4.offline 🔴 源不通时不许说已是最新(u3)", !/已是最新|最新版/.test(offline.text || ""), `「${offline.text}」`);
const retry = await page.$("[data-ui=update-retry]");
V("E4.offline 旁边有「重试」", !!retry && (await retry.isVisible()), "");
await page.screenshot({ path: path.join(out, "e4-10-offline.page.png") });

// ② 源通了,点重试
const srv = spawn(process.execPath, [path.join(here, "serve.mjs"), updDir, port, serveLog], { detached: true, stdio: "ignore" });
srv.unref();
fs.writeFileSync(path.join(out, "e4-serve.pid"), String(srv.pid));
await sleep(1500);
if (retry) await retry.click().catch(() => {});
const got = await waitText(page, "[data-ui=update-status]", /\d+\.\d+\.\d+/, 5000);
console.log(`  点重试后:「${got.text}」`);
// 收起设置弹层 —— 按钮必须在**收起的那一行**上看得见
await page.click("[data-ui=settings-toggle]");
const t0 = Date.now();
let restart = null;
while (Date.now() - t0 < 240000) {
  restart = await page.$("[data-ui=update-restart]");
  if (restart && (await restart.isVisible())) break;
  restart = null;
  await sleep(1000);
}
V("E4.button 下好后,收起的「设置」行上出现「重启以更新」", !!restart, `+${Date.now() - t0}ms`);
await page.screenshot({ path: path.join(out, "e4-11-restart-button.page.png") });
if (!restart) {
  await app.close().catch(() => {});
  console.log(`E4 前半段结束:FAIL ${failed} 条`);
  process.exit(1);
}

// ③ 点它:主进程先收管家,再把位置让给安装器 ⇒ 这一份 Electron 必须自己退出
const proc = app.process();
const exited = new Promise((r) => proc.once("exit", (code) => r(code)));
await restart.click();
const code = await Promise.race([exited, sleep(60000).then(() => "timeout")]);
V("E4.handoff 点「重启以更新」后旧版自己退出(把位置让给安装器)", code !== "timeout", `退出码 ${code}`);
console.log(`E4 前半段结束:FAIL ${failed} 条`);
process.exit(failed ? 1 : 0);
