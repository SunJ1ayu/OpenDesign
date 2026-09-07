// track opendesign-in-app-update e2e:那句"有新版"到底有没有被画到业主眼前。
// 真 chromium + 真 ds_web(不需要 gateway);`/api/update/check` 用 page.route 拦成替身。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 🔴 为什么这一条必须存在(第三轮自审 MR-3):
//    本单其余 52 条判据**全是单元级** —— 它们问的是"这个函数返回哪几个字",
//    一条都问不出"那一行、那个蓝点有没有出现在业主眼前"。这个项目正为这件事栽过:
//    0.91.0 窗口栏整块没画出来,而当时 12 条判据全绿。
//    verify.md 里"这份判据接不住什么"第一条写的就是它 —— 写下来不等于补上了。
//
// 替身是**后端的回答**,不是前端的函数:所以这条链路里 App 的取数、Sidebar 的渲染、
// update.ts 的措辞三段都在真跑,只有网络那一跳是假的。
//
// 跑法:node tests/e2e/update_notice.e2e.mjs(自起 ds_web 于 8842)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8842;
const KEY = "翡翠湾-1801";

const tmp = mkdtempSync(join(tmpdir(), "update-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const home = join(tmp, "home");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
// HOME 隔离 + 一把假 key:否则"还没配 key"的卡片会自动弹出来,遮罩吃掉所有点击
// (2026-08-16 一次 29 条 e2e 齐红就是这么来的,见 tests/e2e/README.md)。
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-fixture\n");
writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-09-07
`);
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, HOME: home, USERPROFILE: home,
         DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

let failures = 0;
async function step(name, fn) {
  console.log(`\n== ${name}`);
  try { await fn(); } catch (e) { failures++; console.error(String(e)); }
}
function expect(cond, label) {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++;
  console.error(`  FAIL: ${label}`);
}

/** 开一页,把 /api/update/check 的回答换成 `body`,并等界面查完那一次。 */
async function pageWith(browser, body) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.route("**/api/update/check*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json",
                    body: JSON.stringify(body) }));
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".side-footer .side-row").waitFor({ timeout: 15000 });
  // 等"查完了"的证据:那一行不再是版本号/检查中。断在界面事实上,不是 sleep。
  await page.waitForFunction(
    () => !document.body.textContent.includes("检查中"), { timeout: 15000 });
  return page;
}

const NEWER = {
  current: "0.98.4", update_available: true, latest: "0.99.0",
  asset: { name: "OpenDesign-Setup-0.99.0.exe", url: "https://x/y", size: 1, digest: null },
  notes: "## 这一版改了什么\n\n修了打开软件时窗口全白的那个 bug",
  error: null,
  release_url: "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.99.0",
};

let browser = null;
try {
  browser = await launchBrowser();

  await step("A 有新版时,收起的设置行上那个蓝点真的被画出来了", async () => {
    const page = await pageWith(browser, NEWER);
    const dot = page.locator(".side-footer .update-dot");
    expect(await dot.count() === 1, "设置那一行上有蓝点(收起状态就看得见)");
    const box = await dot.boundingBox();
    expect(!!box && box.width > 0 && box.height > 0,
      `蓝点有实际尺寸(实测 ${JSON.stringify(box)})—— 0.91 那次整块没画出来,判据全绿`);
    expect(await dot.isVisible(), "蓝点可见(没被别的元素盖掉、没被 display:none)");
    await page.close();
  });

  await step("B 打开设置:那一行说有新版几点几,下载行指向发布页,说明取的是正文", async () => {
    const page = await pageWith(browser, NEWER);
    await page.locator(".side-footer .side-row").click();
    await page.locator(".settings-pop").waitFor({ timeout: 5000 });

    const row = page.locator('.settings-pop button:has-text("检查更新")');
    check(await row.count() === 1, "前提:设置弹层里有且只有一个「检查更新」行");
    const label = (await row.innerText()).replace(/\s+/g, " ");
    expect(label.includes("0.99.0"), `那一行要说是哪一版(实测「${label}」)`);
    expect(!label.includes("已是最新"), `有新版却说已是最新:「${label}」`);

    const dl = page.locator('.settings-pop a.item:has-text("下载")');
    expect(await dl.count() === 1, "有一条能点的下载行");
    const href = await dl.getAttribute("href");
    expect(href === NEWER.release_url, `下载行指向 GitHub 给的发布页(实测 ${href})`);
    const note = (await dl.innerText()).replace(/\s+/g, " ");
    expect(note.includes("白屏") || note.includes("窗口全白"),
      `说明取的是正文而不是「这一版改了什么」那种标题(实测「${note}」)`);
    await page.close();
  });

  await step("C 查不动的时候:没有蓝点,而且绝不许说「已是最新」", async () => {
    const page = await pageWith(browser, {
      current: "0.98.4", update_available: false, latest: null, asset: null,
      notes: "", error: "查更新失败:URLError: no route to host", release_url: null,
    });
    expect(await page.locator(".side-footer .update-dot").count() === 0,
      "查不动的时候不许亮蓝点(那是在说有新版)");
    await page.locator(".side-footer .side-row").click();
    await page.locator(".settings-pop").waitFor({ timeout: 5000 });
    const label = (await page.locator('.settings-pop button:has-text("检查更新")')
      .innerText()).replace(/\s+/g, " ");
    expect(!label.includes("已是最新"),
      `🔴 把失败伪装成成功:「${label}」—— 业主会以为自己在最新版上`);
    expect(label.includes("查不到"), `没说清是"没查成"(实测「${label}」)`);
    await page.close();
  });

  await step("D 有新版但后端没给版本号:一个 null 都不许印给业主(MR-2)", async () => {
    const page = await pageWith(browser, {
      ...NEWER, latest: null, asset: null,
    });
    const dot = page.locator(".side-footer .update-dot");
    check(await dot.count() === 1, "前提:这一格仍然算「有新版」,蓝点该亮");
    const title = await dot.getAttribute("title");
    expect(!/null|undefined/.test(title || ""),
      `蓝点的悬停说明印成「${title}」—— 标签那边(u16)修过同一个组合,这里没修`);

    await page.locator(".side-footer .side-row").click();
    await page.locator(".settings-pop").waitFor({ timeout: 5000 });
    const dl = (await page.locator('.settings-pop a.item:has-text("下载")')
      .innerText()).replace(/\s+/g, " ");
    expect(!/null|undefined/.test(dl), `下载行印成「${dl}」`);
    await page.close();
  });
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条没过`);
process.exit(failures === 0 ? 0 : 1);
