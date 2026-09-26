// track opendesign-sidebar-history e2e(真 chromium + 真 ds_web + 真项目列表;聊天相关接口在页面里用替身)。主 agent 亲写。
//
// 断的是业主眼里的方案一 + 方案二(09-25「直接方案一和方案二一起做吧」):
//   ① 按时间(默认):今天 / 昨天 / 更早 分段;先显示一部分,「显示更多」一直翻到最早的;
//   ② 每条「⋯」:置顶 ⇒ 进「已置顶」、下面不重复;改名 ⇒ 行上是新名字、重开还在;删除(要确认)⇒ 没了,置顶 / 改名一起清;
//   ③ 按项目:每个项目能展开它的对话,碰过两个项目的在两个项目下都出现;项目对话在最前;没碰过项目的在「其他对话」;
//   ④ 切换记住(重开还是按项目);点项目名照旧进工作区;点一条对话回首页接着聊(发 attach)。
// 替身:会话列表 / 对话碰过的项目 / 侧栏状态 / 置顶改名删除 都存在页面的 localStorage 里,重开页面还在(模拟网关那边持久)。
// 代价:替身证明「界面照接口形状做对了」,不证明 ds_web 与网关真的存住 —— 那条由 Python 判据 + QA 执行(真网关)兜。
//
// 跑法:node tests/e2e/sidebar_history.e2e.mjs(自起 ds_web 于 8859;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected, check } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8859;

const STUB = () => {
  const DAY = 86400000;
  const now = Date.now();
  const ago = (ms) => new Date(now - ms).toISOString();
  // 按本机「今天零点」种时间(分段按日期,不是 24 小时滚动):09-26 零点刚过跑,「1 小时前」其实是昨天,整条误红过一次
  const midnight = new Date(now); midnight.setHours(0, 0, 0, 0);
  const m0 = midnight.getTime();
  const today = (frac) => new Date(m0 + (now - m0) * frac).toISOString();          // 今天零点到现在之间
  const at = (ms) => new Date(m0 - ms).toISOString();                               // 今天零点往前
  const seed = () => {
    const sessions = [
      { key: "websocket:k1", title: "客厅吊顶改方案", updated_at: today(0.9) },
      { key: "websocket:k2", title: "主材清单讨论", updated_at: today(0.6) },
      { key: "websocket:k3", title: "天气闲聊", updated_at: today(0.3) },
      { key: "websocket:k4", title: "陈总项目对话", updated_at: at(60 * 60 * 1000) },
      { key: "websocket:k5", title: "昨天的报价", updated_at: at(2 * 60 * 60 * 1000) },
    ];
    for (let i = 1; i <= 25; i++) {
      sessions.push({ key: `websocket:old${i}`, title: `很早的对话${String(i).padStart(2, "0")}`, updated_at: at((2 + i) * DAY) });
    }
    // 网关每 15 分钟空闲压缩一次、把 updated_at 刷成当时(design P6)⇒ 列表里的 updated_at 全是「刚才」;
    // 真正的最后聊天时间由 ds_web 的 session-projects 另给(last_active)
    const lastActive = Object.fromEntries(sessions.map((x) => [x.key, x.updated_at]));
    for (const x of sessions) x.updated_at = ago(60 * 1000);
    return {
      sessions,
      lastActive,
      projects: { "websocket:k1": ["翡翠湾-1801"], "websocket:k2": ["翡翠湾-1801", "陈总办公室"], "websocket:old25": ["翡翠湾-1801"] },
      pinned: [],
      titles: {},
    };
  };
  const load = () => { try { return JSON.parse(localStorage.getItem("__side_stub")) || seed(); } catch { return seed(); } };
  const save = (s) => localStorage.setItem("__side_stub", JSON.stringify(s));
  if (!localStorage.getItem("__side_stub")) save(seed());
  // 项目对话映射(前端既有的 localStorage):k4 是「陈总办公室」的项目对话
  if (!localStorage.getItem("odw.projectThreads")) localStorage.setItem("odw.projectThreads", JSON.stringify({ "陈总办公室": "k4" }));
  window.__attached = [];
  window.__sidebarPosts = [];
  const json = (obj, status = 200) => Promise.resolve(new Response(JSON.stringify(obj),
    { status, headers: { "Content-Type": "application/json" } }));
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    const s = load();
    if (u.includes("/api/chat/bootstrap")) return json({ token: "stub", ws_path: "/ws", expires_in: 600, model_name: "stub" });
    if (u.includes("/api/chat/sessions?") || u.endsWith("/api/chat/sessions")) return json({ sessions: s.sessions });
    if (u.includes("/api/chat/session-projects")) return json({ sessions: s.projects, last_active: s.lastActive });
    if (u.includes("/api/chat/sidebar-state")) return json({ pinned_keys: s.pinned, title_overrides: s.titles });
    const m = u.match(/\/api\/chat\/sessions\/([^/]+)\/(pin|rename|delete|thread)/);
    if (m) {
      const key = decodeURIComponent(m[1]);
      const body = init && init.body ? JSON.parse(init.body) : {};
      if (m[2] === "thread") return json({ messages: [{ id: "u1", role: "user", content: "之前说过的话", turnId: "t1" }] });
      window.__sidebarPosts.push({ key, op: m[2], body });
      if (m[2] === "pin") {
        s.pinned = s.pinned.filter((k) => k !== key);
        if (body.pinned) s.pinned.push(key);
      } else if (m[2] === "rename") {
        const t = typeof body.title === "string" ? body.title.trim() : "";
        if (t) s.titles[key] = t.slice(0, 160); else delete s.titles[key];
      } else if (m[2] === "delete") {
        s.sessions = s.sessions.filter((x) => x.key !== key);
        s.pinned = s.pinned.filter((k) => k !== key);
        delete s.titles[key];
        save(s);
        return json({ deleted: true });
      }
      save(s);
      return json({ pinned_keys: s.pinned, title_overrides: s.titles });
    }
    return origFetch(url, init);
  };
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      setTimeout(() => { this.readyState = StubWS.OPEN; this.onopen?.({}); this._emit({ event: "ready", chat_id: "fresh" }); }, 10);
    }
    send(data) {
      const m = JSON.parse(data);
      if (m.type === "attach") {
        window.__attached.push(m.chat_id);
        setTimeout(() => this._emit({ event: "attached", chat_id: m.chat_id }), 10);
      }
    }
  }
  window.WebSocket = StubWS;
};

const tmp = mkdtempSync(join(tmpdir(), "sidebar-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
// 三个建档项目(档案 + 工作区文件夹;照 frontend_p2_polish / cockpit 的写法)。
// 09-25 修:原先只登记了文件夹、没写档案 ⇒ /api/projects 回空(改动前后都空),项目栏的三条断言在结构上就问不出来。
const STAGE = { "翡翠湾-1801": "施工跟进", "陈总办公室": "方案深化", "滨江-12F": "洽谈" };
for (const p of ["翡翠湾-1801", "陈总办公室", "滨江-12F"]) {
  mkdirSync(join(ws, p), { recursive: true });
  writeFileSync(join(dsRoot, "projects", `${p}.md`),
    `# ${p}\n\n- 业主: [[李四]]\n- 阶段: ${STAGE[p]}\n\n## 变更记录\n\n## 沟通日志\n\n---\n最后更新: 2026-09-20\n`);
}
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".", projects: { "翡翠湾-1801": "翡翠湾-1801", "陈总办公室": "陈总办公室", "滨江-12F": "滨江-12F" },
}));
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-sidebar\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));

let failures = 0;
let browser = null;
let srv = null;
const step = async (label, fn) => {
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};
async function until(fn, timeoutMs = 8000, stepMs = 100) {
  const t0 = Date.now();
  for (;;) {
    try { if (await fn()) return true; } catch { /* 还没出现 */ }
    if (Date.now() - t0 > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, stepMs));
  }
}

try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath, HOME: home, USERPROFILE: home },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
  }
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  page.on("dialog", (d) => d.accept());
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await waitConnected(page, ".home-pane");
  const side = page.locator("nav.side");
  const rowsIn = (sel) => page.locator(`${sel} .hist-row`);
  const texts = async (sel) => (await rowsIn(sel).allInnerTexts()).map((t) => t.split("\n")[0].trim());

  await step("① 按时间(默认):今天 / 昨天 / 更早 分段;先显示一部分,「显示更多」翻到最早的", async () => {
    await page.locator('[data-ui="side-day"]').first().waitFor({ timeout: 10000 });
    check((await page.locator('[data-ui="side-view-time"]').getAttribute("aria-pressed")) === "true", "默认是按时间");
    const days = (await page.locator('[data-ui="side-day"]').allInnerTexts()).map((t) => t.trim());
    check(JSON.stringify(days) === JSON.stringify(["今天", "昨天", "更早"]), `分段:${JSON.stringify(days)}`);
    const first = await rowsIn('[data-ui="side-history"]').count();
    check(first > 2 && first < 30, `先显示一部分(不是只有 2 条,也不是一下全摊开):${first}`);
    for (let i = 0; i < 5 && (await page.locator('[data-ui="side-more"]').count()) > 0; i++) {
      await page.locator('[data-ui="side-more"]').first().click();
    }
    check(await until(async () => (await texts('[data-ui="side-history"]')).includes("很早的对话25")), "翻到了最早的那条");
    check((await rowsIn('[data-ui="side-history"]').count()) === 30, "30 条都看得到");
    const proj = await side.locator(".proj-row").count();
    check(proj === 3, `下面的项目栏照旧(3 个项目):${proj}`);
    // QA DeepSeek / GLM:「翡翠湾-1801 +1」看不出另一个是哪个 ⇒ 小标悬停列出全部项目名
    const tagTitle = await page.locator('[data-ui="side-history"] .hist-row', { hasText: "主材清单讨论" }).first()
      .locator(".hist-proj").getAttribute("title");
    check(!!tagTitle && tagTitle.includes("翡翠湾-1801") && tagTitle.includes("陈总办公室"), `小标悬停列出全部项目:${tagTitle}`);
    // 4c C5:历史翻开 30 条之后,左下角设置不能被挤出屏幕,项目栏要滚得到
    const setBox = await page.locator('[data-ui="settings-toggle"]').boundingBox();
    check(!!setBox && setBox.y >= 0 && setBox.y + setBox.height <= 900, `左下角设置还在屏幕里:${JSON.stringify(setBox)}`);
    const lastProj = side.locator(".proj-row").last();
    await lastProj.scrollIntoViewIfNeeded();
    const pb = await lastProj.boundingBox();
    const setBox2 = await page.locator('[data-ui="settings-toggle"]').boundingBox();
    check(!!pb && pb.y >= 0 && pb.y + pb.height <= (setBox2 ? setBox2.y : 900),
      `项目栏滚得到、且不被设置那一行盖住:${JSON.stringify({ pb, setBox2 })}`);
  });

  await step("② ⋯ 置顶 ⇒ 进「已置顶」,下面不重复", async () => {
    const row = page.locator('[data-ui="side-history"] .hist-row', { hasText: "客厅吊顶改方案" }).first();
    await row.hover();
    await row.locator('[data-ui="hist-menu"]').click();
    await page.locator('[data-ui="hist-pin"]').click();
    check(await until(async () => (await texts('[data-ui="side-pinned"]')).includes("客厅吊顶改方案")), "进了「已置顶」");
    check(!(await texts('[data-ui="side-history"]')).includes("客厅吊顶改方案"), "下面的列表里不再重复");
  });

  await step("② ⋯ 改名:清空回车 = 取消,名字不变(QA Grok TC-10)", async () => {
    const row = page.locator('[data-ui="side-history"] .hist-row', { hasText: "昨天的报价" }).first();
    await row.hover();
    await row.locator('[data-ui="hist-menu"]').click();
    await page.locator('[data-ui="hist-rename"]').click();
    const input = page.locator('[data-ui="hist-rename-input"]');
    await input.fill("   ");
    await input.press("Enter");
    check(await until(async () => (await page.locator('[data-ui="hist-rename-input"]').count()) === 0), "改名框关了");
    check((await texts('[data-ui="side-history"]')).includes("昨天的报价"), "名字没变");
    check(!(await page.evaluate(() => window.__sidebarPosts)).some((p) => p.op === "rename"), "没发改名请求");
  });

  await step("② ⋯ 改名 ⇒ 行上是新名字;重开还在", async () => {
    const row = page.locator('[data-ui="side-history"] .hist-row', { hasText: "昨天的报价" }).first();
    await row.hover();
    await row.locator('[data-ui="hist-menu"]').click();
    await page.locator('[data-ui="hist-rename"]').click();
    const input = page.locator('[data-ui="hist-rename-input"]');
    await input.fill("  王女士报价 ");
    await input.press("Enter");
    check(await until(async () => (await texts('[data-ui="side-history"]')).includes("王女士报价")), "行上是新名字(去了首尾空格)");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="side-day"]').first().waitFor({ timeout: 10000 });
    check(await until(async () => (await texts('[data-ui="side-history"]')).includes("王女士报价")), "重开还是新名字");
    check((await texts('[data-ui="side-pinned"]')).includes("客厅吊顶改方案"), "重开置顶还在");
  });

  await step("③ 按项目:两个项目下都出现;项目对话在最前;其他对话;置顶的不在项目下", async () => {
    await page.locator('[data-ui="side-view-project"]').click();
    // QA Gemini:项目行上待办数与对话数两个裸数字挨着分不清 ⇒ 对话数带对话图标、读屏名说明是「几段对话」
    const exp = page.locator('[data-ui="proj-expand"][data-project="翡翠湾-1801"]');
    check((await exp.locator("svg").count()) === 1, "对话数前有对话图标");
    check(/段对话/.test((await exp.getAttribute("aria-label")) || ""), `对话数的读屏名:${await exp.getAttribute("aria-label")}`);
    for (const p of ["翡翠湾-1801", "陈总办公室"]) {
      await page.locator(`[data-ui="proj-expand"][data-project="${p}"]`).click();
    }
    const fcw = await texts('[data-ui="proj-sessions"][data-project="翡翠湾-1801"]');
    const chen = await texts('[data-ui="proj-sessions"][data-project="陈总办公室"]');
    check(fcw.includes("主材清单讨论") && chen.includes("主材清单讨论"), `碰过两个项目的在两个项目下都有:${JSON.stringify({ fcw, chen })}`);
    check(chen[0] === "陈总项目对话", `项目对话在最前:${JSON.stringify(chen)}`);
    check(!fcw.includes("客厅吊顶改方案"), "置顶的不在项目下重复");
    const other = await texts('[data-ui="side-other"]');
    check(other.includes("天气闲聊") && !other.includes("主材清单讨论"), `其他对话:${JSON.stringify(other.slice(0, 5))}`);
  });

  await step("④ 切换记住;点项目名照旧进工作区", async () => {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="side-view-project"]').waitFor({ timeout: 10000 });
    check((await page.locator('[data-ui="side-view-project"]').getAttribute("aria-pressed")) === "true", "重开还是按项目");
    await side.locator(".proj-row", { hasText: "滨江-12F" }).first().click();
    check(await until(async () => (await page.evaluate(() => location.hash)) === "#/workspace"), "点项目名进工作区");
  });

  await step("④ 点一条对话回首页接着聊(发 attach)", async () => {
    await page.locator('[data-ui="side-other"] .hist-row', { hasText: "天气闲聊" }).first().click();
    check(await until(async () => (await page.evaluate(() => window.__attached)).includes("k3")), "挂回了那段对话");
    check(await until(async () => (await page.evaluate(() => location.hash)) === "#/" || (await page.evaluate(() => location.hash)) === ""), "回到首页");
  });

  await step("② ⋯ 删除(确认)⇒ 没了,置顶 / 改名一起清", async () => {
    await page.locator('[data-ui="side-view-time"]').click();
    const row = page.locator('[data-ui="side-pinned"] .hist-row', { hasText: "客厅吊顶改方案" }).first();
    await row.hover();
    await row.locator('[data-ui="hist-menu"]').click();
    await page.locator('[data-ui="hist-delete"]').click();
    check(await until(async () => !(await texts('[data-ui="side-pinned"]')).includes("客厅吊顶改方案")), "置顶区里没了");
    check(!(await texts('[data-ui="side-history"]')).includes("客厅吊顶改方案"), "列表里也没了");
    const posts = await page.evaluate(() => window.__sidebarPosts);
    check(posts.some((p) => p.op === "delete" && p.key === "websocket:k1"), "删的是这一条");
  });

  check(errs.length === 0, `页面无未捕获异常:${errs.join(" | ")}`);
} catch (e) {
  failures += 1;
  console.log(`  not ok - 场景中断: ${e.message}`);
} finally {
  await browser?.close();
  srv?.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "sidebar_history.e2e: OK" : `sidebar_history.e2e: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
