// 业主同意卡 e2e(真 chromium + 真 ds_web)。主 agent 亲写,执行腿逐字节 off-limits。
// track opendesign-owner-consent。
//
// 这条补的是 tests/test_ds_consent.py 里**明账暂缓**的那一条。攻题第 2 条指出
// 「GET 卡片接口可以自动批准」时,后端那一半我用 O8a(反复 GET 前后快照逐字节相同)
// 堵住了,但**前端那一半 python 判据看不见**:页面上的 JavaScript 完全可以在拿到
// 卡片之后自己 POST 一个 approve,业主一次都没点,而后端每一条断言都是绿的。
//
// 覆盖:
//   A 有待确认时卡片出现,且**影响面那句话真的在屏幕上**(不是只有"助手请求权限")
//     —— 这道闸的强度就等于业主看不看得懂他在批什么,文案是它的承重墙。
//   B **卡片加载完、业主没点任何东西时,一个 resolve 请求都不许发出去**(首要理由)。
//   C 点「拒绝」→ workspace.json 逐字节没变,卡片消失。
//   D 「拒绝」占主按钮位 —— 安全闸的刻意不对称(拿不准时的正确动作是拒绝)。
//
// 跑法:node tests/e2e/consent_card.e2e.mjs(自起 ds_web 于 8831)
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8831;

const tmp = mkdtempSync(join(tmpdir(), "consent-e2e-"));
const dsRoot = join(tmp, "ds");
const oldRoot = join(tmp, "old");
const newRoot = join(tmp, "new");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(oldRoot, "01-项目", "翡翠湾-1801"), { recursive: true });
mkdirSync(join(newRoot, "01-项目", "机密别墅"), { recursive: true });

const cfgPath = join(dsRoot, "config", "workspace.json");
writeFileSync(cfgPath, JSON.stringify(
  { root: oldRoot, projects: {}, projectsDir: "01-项目" }, null, 2));

// 排一条真的待确认:走**核心函数**,不手写 pending json —— 手写的夹具会跟真实
// 结构漂移,而这条 e2e 的价值正在于它验的是真链路。
const staged = spawnSync("python3", ["-c", `
import sys; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_tools
r = ds_tools.set_workspace(${JSON.stringify(newRoot)}, ds_root=${JSON.stringify(dsRoot)})
assert r.get("pending"), r
print(r["pending_id"])
`], { encoding: "utf-8" });
const pendingId = (staged.stdout || "").trim();
if (!/^\d{8}-\d{6}-[0-9a-f]{6}$/.test(pendingId)) {
  console.error("夹具没排上待确认:", staged.stdout, staged.stderr);
  process.exit(1);
}
const cfgBefore = readFileSync(cfgPath, "utf-8");

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
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

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 探针装在打开页面**之前**:要抓的就是"页面自己发的那一发"。
  const resolveCalls = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/consent/resolve")) resolveCalls.push(req.method());
  });

  const card = page.locator('[data-ui="consent-card"]');

  await step("A 卡片出现,并且把影响面说清楚了", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await card.waitFor({ timeout: 15000 });
    const text = await card.innerText();
    expect(text.includes(newRoot), "卡上写明了它想改成哪个根(路径原样可见)");
    expect(text.includes("资料文档") && text.includes("上传到大模型"),
      "卡上写明了影响面:同意后能读到什么、内容会上云");
  });

  await step("B 业主没点之前,一个 resolve 请求都没发出去", async () => {
    await page.waitForTimeout(2000);   // 给"自动批准"充分暴露的机会
    expect(resolveCalls.length === 0, `没有自动发出批准请求(实际 ${JSON.stringify(resolveCalls)})`);
    expect(readFileSync(cfgPath, "utf-8") === cfgBefore, "workspace.json 逐字节未变");
  });

  await step("D 「拒绝」占主按钮位(安全闸的刻意不对称)", async () => {
    const first = card.locator('[data-ui="consent-item"] button').first();
    expect((await first.innerText()).trim() === "拒绝", "第一个按钮是「拒绝」");
    expect(await first.evaluate((b) => b.classList.contains("btn-primary")),
      "「拒绝」用的是主按钮角色(btn-primary)");
  });

  await step("C 点「拒绝」→ 不落盘,卡片消失", async () => {
    await card.locator('[data-ui="consent-item"] button').first().click();
    await card.waitFor({ state: "detached", timeout: 8000 });
    expect(readFileSync(cfgPath, "utf-8") === cfgBefore,
      "拒绝之后 workspace.json 仍然逐字节未变");
    expect(resolveCalls.length === 1, `恰好发了一次 resolve(实际 ${resolveCalls.length})`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
