// 判据:设置页 · 模型设置(照 ZCode)端到端(track opendesign-zcode-model-settings)。主 agent 亲写,判据先单独 commit。
// 真 chromium + 真 ds_web + 假外壳(应答重启暗号并做 prepare_gateway)+ 一个本机假厂商(给「测试」和自定义供应商用)。
// 用例出处:tracks/opendesign-zcode-model-settings/evidence/acceptance-cases.md(下面每条标着 A 号);钩子表在 design.md。
//
// 🔴 这份判据**不许有外网出口**(判据不许花钱、不许连外网的老规矩):「测试」只点在本机假厂商的模型上;
//    内置厂商的「测试」按钮只问在不在,不点。
//
// 它问不出:ZCode 像不像(→ T5 截图亲看 + QA-执行);真厂商真能连上(→ 业主真机)。
//
// 跑法:node tests/e2e/model_settings.e2e.mjs(自起 ds_web 于 8851;不需要 nanobot 网关)
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { createServer as createHttpServer } from "node:http";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8851;
const PY = process.env.PY || "/root/.venvs/design-studio/bin/python";
const MIMO_KEY = "tp-e2e-ms-mimo-0123456789abcdef";
const DS_KEY = "sk-e2e-ms-deepseek-0123456789ab";
const CUSTOM_KEY = "sk-e2e-ms-custom-0123456789abcd";
const KEYS = [MIMO_KEY, DS_KEY, CUSTOM_KEY];
let failures = 0;

async function until(fn, timeoutMs = 15000, stepMs = 200) {
  const t0 = Date.now();
  for (;;) {
    try { if (await fn()) return true; } catch { /* 还没出现 */ }
    if (Date.now() - t0 > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, stepMs));
  }
}
function check(ok, label) {
  if (ok) console.log(`  ok   - ${label}`);
  else { console.log(`  FAIL - ${label}`); failures += 1; }
}

// 期望值的唯一出处是后端目录(不在判据里另抄一份端点/模型名/链接)
const catRaw = spawnSync(PY, ["-c", `
import sys, json; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
print(json.dumps(ds_credential.PROVIDERS, ensure_ascii=False))
`], { encoding: "utf-8" });
const CATALOG = JSON.parse(catRaw.stdout || "{}");
if (!CATALOG.mimo || !CATALOG.deepseek || !CATALOG.kimi) {
  console.error("读不到后端厂商目录:", catRaw.stderr);
  process.exit(1);
}

const STUB = () => {
  window.__wsAll = [];
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      return Promise.resolve(new Response(JSON.stringify(
        { token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "mimo-v2.5" }),
        { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    if (u.includes("/thread")) return Promise.resolve(new Response("not found", { status: 404 }));
    return origFetch(url, init);
  };
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      window.__wsAll.push(this);
      setTimeout(() => {
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: `chat-ms-${window.__wsAll.length}` });
      }, 10);
    }
    send() { /* 这个场景不聊天 */ }
  }
  window.WebSocket = StubWS;
};

// ── 台面(与 per_vendor_keys 同款:已配 MiMo 的老家)──
const tmp = mkdtempSync(join(tmpdir(), "ds-e2e-model-settings-"));
const dsRoot = join(tmp, "ds");
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(tmp, "ws"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: join(tmp, "ws"), projects: {} }));
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), MIMO_KEY + "\n");
mkdirSync(dirname(cfgPath), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));
const readCfg = () => JSON.parse(readFileSync(cfgPath, "utf8"));
const currentModel = () => {
  const cfg = readCfg();
  const name = cfg.agents?.defaults?.modelPreset;
  return name ? cfg.model_presets?.[name]?.model ?? null : cfg.agents?.defaults?.model ?? null;
};

// ── 假外壳:认暗号、回 OK,然后(晚 1.5 秒)做外壳起网关时的那一步 ──
const HELLO = "OpenDesign.ds_shell_core.lock.v1\n";
const restarts = [];
const frames = [];              // 外壳收到的每一帧的动词(track opendesign-key-restart:网关在跑时一帧都不该有)
const fakeShell = createServer((sock) => {
  let buf = "";
  sock.on("data", (b) => {
    buf += b.toString("utf8");
    if (buf.startsWith(HELLO) && buf.slice(HELLO.length).includes("\n")) {
      const verb = buf.slice(HELLO.length).split("\n")[0];
      frames.push(verb);
      if (verb === "RESTART-BACKEND") {
        sock.end("OK RESTART-BACKEND\n");
        setTimeout(() => {
          const r = spawnSync(PY, ["-c", `
import sys; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
print(sorted(ds_credential.prepare_gateway(${JSON.stringify(home)}, ${JSON.stringify(cfgPath)})))
`], { encoding: "utf-8" });
          restarts.push({ rc: r.status, err: (r.stderr || "").trim() });
        }, 1500);
      } else {
        sock.end("OK\n");
      }
    }
  });
});
await new Promise((r) => fakeShell.listen(0, "127.0.0.1", r));

// ── 假网关端口(track opendesign-key-restart):ds_web 存完 key 看「网关端口在不在听」判 live / 请外壳起。
//    显式给它一个我们管的端口 —— 不给就落到默认 8765,那上面有没有人听取决于跑判据的机器(开发机上真有一个网关在听)。
//    聊天那条 websocket 在页面里是替身(_ws-stub),这个端口只影响 ds_web 的判法。
const fakeGw = createServer((s) => s.destroy());
await new Promise((r) => fakeGw.listen(0, "127.0.0.1", r));
const GW_PORT = fakeGw.address().port;

// ── 本机假厂商:只认 CUSTOM_KEY、只认 gpt-e2e ──
const vendorSeen = [];
const fakeVendor = createHttpServer((req, res) => {
  let raw = "";
  req.on("data", (b) => { raw += b; });
  req.on("end", () => {
    let body = {};
    try { body = JSON.parse(raw || "{}"); } catch { /* 坏包 */ }
    vendorSeen.push({ path: req.url, model: body.model, auth: req.headers.authorization === `Bearer ${CUSTOM_KEY}` });
    const send = (code, obj) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); };
    if (req.headers.authorization !== `Bearer ${CUSTOM_KEY}`) return send(401, { error: { message: "invalid api key" } });
    if (body.model !== "gpt-e2e") return send(404, { error: { message: "model not found" } });
    send(200, { id: "x", object: "chat.completion", model: "gpt-e2e",
                choices: [{ index: 0, message: { role: "assistant", content: "ok" }, finish_reason: "stop" }] });
  });
});
await new Promise((r) => fakeVendor.listen(0, "127.0.0.1", r));
const VENDOR_BASE = `http://127.0.0.1:${fakeVendor.address().port}/v1`;

const pane = ".home-pane";
const chip = `${pane} .chat-card [data-ui="chat-model"]`;
const menu = `${pane} [data-ui="chat-model-menu"]`;
const MS = '[data-ui="model-settings"]';
let browser = null;
let srv = null;
const WATCHDOG = setTimeout(() => {
  console.log("\n  FAIL - 判据自己超时(300s):没跑完就没有结论,别当它是绿的");
  try { srv?.kill("SIGKILL"); } catch { /* 已经没了 */ }
  process.exit(1);
}, 300_000);
WATCHDOG.unref();

try {
  srv = spawn(PY, [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath,
           HOME: home, USERPROFILE: home, DS_LLM_KEY: "", DS_SHELL_LOCK_PORT: String(fakeShell.address().port),
           DS_NANOBOT_PORT: String(GW_PORT),
           DS_WEB_DIST: join(ROOT, "web", "dist") },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const srvOut = [];
  srv.stdout.on("data", (b) => srvOut.push(String(b)));
  srv.stderr.on("data", (b) => srvOut.push(String(b)));
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch {
      if (i > 75) throw new Error("ds_web 起不来");
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 960 } });
  page.setDefaultTimeout(10_000);
  const consoleLines = [];
  const bodies = [];
  page.on("console", (m) => consoleLines.push(m.text()));
  page.on("pageerror", (e) => consoleLines.push(`PAGEERROR ${e}`));
  page.on("response", async (r) => { try { bodies.push(await r.text()); } catch { /* 拿不到 */ } });
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
  await waitConnected(page, pane);

  const navItem = (id) => page.locator(`${MS} [data-ui="ms-nav-item"][data-provider="${id}"]`);
  const detail = (id) => page.locator(`${MS} [data-ui="ms-detail"][data-provider="${id}"]`);
  const modelRow = (id, m) => detail(id).locator(`[data-ui="ms-model"][data-model="${m}"]`);
  const notice = () => page.locator(`${MS} [data-ui="ms-notice"]:visible`).innerText().catch(() => "");
  const openSettings = async (provider) => {
    await page.goto(`${base}/#/settings/models${provider ? `?provider=${provider}` : ""}`, { waitUntil: "domcontentloaded" });
    await page.locator(MS).waitFor({ timeout: 10000 });
    if (provider) await detail(provider).waitFor({ timeout: 8000 });
  };
  const select = async (provider) => {
    await navItem(provider).click();
    await detail(provider).waitFor({ timeout: 8000 });
  };
  const backToChat = async () => {
    await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
    await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
    await waitConnected(page, pane);
  };
  // 两级菜单:打开 → 等这次 /api/llm/models 落地 → 返回每家 {selected, models[]}(逐家悬停读子菜单)
  const menuTree = async () => {
    const fresh = page.waitForResponse((r) => r.url().includes("/api/llm/models"), { timeout: 8000 });
    await page.locator(chip).click();
    const body = await (await fresh).json().catch(() => ({}));
    const want = Array.isArray(body.groups) && body.groups.length ? body.groups.length : (body.models?.length ? 1 : 0);
    await page.locator(menu).waitFor({ state: "visible", timeout: 5000 });
    await until(async () => (await page.locator(`${menu} [data-ui="chat-model-vendor"]`).count()) === want, 5000);
    const out = {};
    for (const id of await page.locator(`${menu} [data-ui="chat-model-vendor"]`).evaluateAll(
      (els) => els.map((e) => e.getAttribute("data-provider")))) {
      const row = page.locator(`${menu} [data-ui="chat-model-vendor"][data-provider="${id}"]`);
      await row.hover();
      const sub = page.locator(`[data-ui="chat-model-sub"][data-provider="${id}"]`);
      await sub.waitFor({ state: "visible", timeout: 5000 });
      out[id] = { selected: await row.getAttribute("data-selected") === "true",
                  models: await sub.locator("[data-model-id]").evaluateAll((els) => els.map((e) => e.getAttribute("data-model-id"))) };
    }
    return out;
  };
  const pickInMenu = async (provider, model) => {
    await menuTree();
    await page.locator(`${menu} [data-ui="chat-model-vendor"][data-provider="${provider}"]`).hover();
    await page.locator(`[data-ui="chat-model-sub"][data-provider="${provider}"] [data-model-id="${model}"]`).click();
    return until(() => currentModel() === model, 8000);
  };
  const addModel = async (provider, id, ctx) => {
    await detail(provider).locator('[data-ui="ms-add-model"]').click();
    const dlg = page.locator('[data-ui="ms-model-dialog"]');
    await dlg.waitFor({ timeout: 5000 });
    await dlg.locator('[data-ui="ms-model-id"]').fill(id);
    await dlg.locator('[data-ui="ms-model-ctx"]').fill(ctx);
    await dlg.locator('[data-ui="ms-dialog-save"]').click();
    return dlg;
  };

  // ── 结构(A22 / A21 / A28 / A1 / A16 / A5)──
  await openSettings(null);
  const groups = await page.locator(`${MS} [data-ui="ms-group"]`).evaluateAll(
    (els) => els.map((e) => [e.getAttribute("data-group"), e.innerText]));
  check(groups.length === 2 && groups[0][0] === "builtin" && /内置供应商/.test(groups[0][1])
        && groups[1][0] === "custom" && /自定义供应商/.test(groups[1][1]),
    `A22 左栏两组:内置供应商 / 自定义供应商(实际 ${JSON.stringify(groups.map((g) => g[0]))})`);
  const builtinIds = await page.locator(`${MS} [data-ui="ms-group"][data-group="builtin"] [data-ui="ms-nav-item"]`)
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-provider")));
  check(JSON.stringify(builtinIds) === JSON.stringify(Object.keys(CATALOG)), `A22 内置五家、照后端顺序(实际 ${JSON.stringify(builtinIds)})`);
  check(await navItem("mimo").locator('[data-provider-status="ready"]').count() === 1
        && await navItem("deepseek").locator('[data-provider-status="unavailable"]').count() === 1,
    "A22 状态点:有 key 且后台拿到 = 就绪;没填 = 未就绪");
  check(await page.locator(`${MS} [data-ui="ms-add-provider"]:visible`).count() === 1
        && await page.locator(`${MS} [data-ui="ms-refresh"]:visible`).count() === 1,
    "A22 顶上有「刷新」和「添加供应商」(有外壳)");
  await select("mimo");
  const baseInput = detail("mimo").locator('[data-ui="ms-base"]');
  check(await baseInput.inputValue() === CATALOG.mimo.apiBase && !(await baseInput.isEditable()),
    "A21 内置厂商的 Base URL 看得见、改不了");
  await select("glm_plan");
  await select("glm");
  check(await navItem("glm_plan").innerText() !== await navItem("glm").innerText(), "A5 GLM 套餐 / 按量是两行、名字不同");
  await select("kimi");
  const link = detail("kimi").locator('[data-ui="ms-key-link"]');
  check(await link.getAttribute("href") === CATALOG.kimi.keyUrl && /^https:\/\//.test(CATALOG.kimi.keyUrl)
        && await link.getAttribute("target") === "_blank" && /noreferrer/.test(await link.getAttribute("rel") || "")
        && /获取/.test(await link.innerText()),
    "A28 「获取 API Key」跟着选中的那家、https、新窗口开、不带来源(接替 ku3)");
  await select("mimo");
  const mimoModels = await detail("mimo").locator('[data-ui="ms-model"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-model")));
  check(CATALOG.mimo.models.every((m) => mimoModels.includes(m)) && mimoModels.includes("mimo-v2.6-pro") && mimoModels.includes("mimo-v2.6-flash"),
    `A1 小米的模型列表里有 v2.6-pro / v2.6-flash(实际 ${JSON.stringify(mimoModels)})`);
  check(await modelRow("mimo", "mimo-v2.5").locator('[data-ui="ms-delete"]').count() === 0
        && await modelRow("mimo", "mimo-v2.5").locator('[data-ui="ms-test"]').count() === 1,
    "A16 内置模型没有「删除」,有「测试」");

  // ── 添加模型:拒收(A18)→ 收下(A2)──
  for (const [id, ctx, why] of [["", "", "空 ID"], ["bad id", "", "带空格"], ["mimo-v2.5", "", "重复"],
                                 ["mimo-e2e", "abc", "上下文不是数字"], ["mimo-e2e", "12", "上下文太小"]]) {
    const dlg = await addModel("mimo", id, ctx);
    const err = await until(() => dlg.locator('[data-ui="ms-dialog-error"]').isVisible(), 5000)
      ? await dlg.locator('[data-ui="ms-dialog-error"]').innerText() : "";
    check(err.trim().length > 0 && await modelRow("mimo", "mimo-e2e").count() === 0,
      `A18 添加模型${why} ⇒ 说人话、不新增(实际「${err.trim()}」)`);
    await page.keyboard.press("Escape");
    await until(async () => !(await dlg.isVisible()), 3000);
  }
  await addModel("mimo", "mimo-e2e", "262144");
  check(await until(() => modelRow("mimo", "mimo-e2e").isVisible(), 8000)
        && /^262\.1K$/.test((await modelRow("mimo", "mimo-e2e").locator('[data-ui="ms-ctx"]').innerText().catch(() => "")).trim()),
    "A2 添加模型 ⇒ 列表里多一行,上下文照 ZCode 写成 262.1K(K6)");
  check(await modelRow("mimo", "mimo-e2e").locator('[data-ui="ms-delete"]').count() === 1, "A16 自己加的模型有「删除」");
  // 09-24 第 1 轮评审 #5(MiMo MIN-3):已保存的提示是「首四…末四」,悬停字不许说「只显示末四位」
  {
    const eyeTitle = await detail("mimo").locator('[data-ui="ms-key-eye"]').getAttribute("title");
    check(!!eyeTitle && !/末四位/.test(eyeTitle), `#5 「显示」按钮悬停字不再说「只显示末四位」(实际「${eyeTitle}」)`);
  }
  // 09-24 QA-执行 K5(DS D5):内置行没有「删除」时,「测试 / 编辑」不许整体右移、和自加模型行错开一列
  {
    const xOf = async (m) => (await modelRow("mimo", m).locator('[data-ui="ms-test"]').boundingBox())?.x ?? NaN;
    const [xb, xc] = [await xOf(CATALOG.mimo.model), await xOf("mimo-e2e")];
    const noDel = await modelRow("mimo", CATALOG.mimo.model).locator('[data-ui="ms-delete"]').count() === 0;
    check(noDel && Math.abs(xb - xc) <= 1, `K5 内置行(没有删除)与自加行的「测试」在同一列(内置 x=${xb},自加 x=${xc},内置无删除=${noDel})`);
  }

  // ── 聊天框能选到它;在用的模型删不掉、在用的那家禁不掉(A2 / A6)──
  await backToChat();
  check(await pickInMenu("mimo", "mimo-e2e"), "A2 聊天框换模型里选得到刚加的模型,配置真的换过去");
  await openSettings("mimo");
  await modelRow("mimo", "mimo-e2e").locator('[data-ui="ms-delete"]').click();
  check(await until(async () => /正在用/.test(await notice()), 5000) && await modelRow("mimo", "mimo-e2e").count() === 1
        && currentModel() === "mimo-e2e",
    `A6 正在用的模型删不掉,说人话、当前不变(提示「${await notice()}」)`);
  const enable = detail("mimo").locator('[data-ui="ms-enable"]');
  await enable.click();
  check(await until(async () => /正在用/.test(await notice()), 5000) && await enable.getAttribute("aria-checked") === "true",
    `A6 正在用的那家禁不掉,开关不动(提示「${await notice()}」)`);
  // 09-24 QA-执行 K4(两家):这句拒绝提示不许挂到下一件不相干的事(添加供应商弹窗)后面
  await page.locator(`${MS} [data-ui="ms-add-provider"]`).click();
  await page.locator('[data-ui="ms-provider-form"]').waitFor({ timeout: 5000 });
  check(!/正在用/.test(await notice()), `K4 打开添加供应商后,上一句拒绝提示已收起(实际「${await notice()}」)`);
  await page.keyboard.press("Escape");
  await until(async () => !(await page.locator('[data-ui="ms-provider-form"]').isVisible()), 3000);

  // ── 存另一家 key(A3;09-25 track opendesign-key-restart 改写):网关在跑 ⇒ 不找外壳、不重启,
  //    存完当场就绪、进换模型菜单;不换当前;提示告诉他去右下角换,不说「下一句就用」(QA 设计 d5)。
  //    原来这里问的是「提示正在重启 / 重启完才进菜单 / 就绪后改口已开始」—— 那是存 key 要重启网关时的契约,
  //    业主 09-25 拍板改成照 ZCode 存了就用;网关真用上没有由 tests/test_key_live.py L1 在真网关上问。
  await select("deepseek");
  const framesA3 = frames.length;
  await detail("deepseek").locator('[data-ui="ms-key"]').fill(DS_KEY);
  await detail("deepseek").locator('[data-ui="ms-key-save"]').click();
  check(await until(async () => /右下角/.test(await notice()), 5000) && !/重启|下一句|稍等/.test(await notice()),
    `A3 存另一家:提示说去右下角换,不提重启、不说下一句就用(「${await notice()}」)`);
  const early = await (await fetch(`${base}/api/llm/models`)).json();
  check((early.groups || []).some((g) => g.provider === "deepseek"), "A3/A15 存完当场进换模型菜单(网关现读 key 文件,不等重启)");
  check(await until(() => navItem("deepseek").locator('[data-provider-status="ready"]').count().then((n) => n === 1), 5000),
    "A3 存完当场就绪");
  await page.waitForTimeout(500);
  check(frames.length === framesA3, `A3 网关在跑 ⇒ 一帧都没发给外壳(实际 ${JSON.stringify(frames.slice(framesA3))})`);
  check(currentModel() === "mimo-e2e", "A3 存别家的 key 没换当前模型(D4)");

  // ── 禁用 / 启用(A7)──
  await select("deepseek");
  await detail("deepseek").locator('[data-ui="ms-enable"]').click();
  check(await until(() => navItem("deepseek").locator('[data-provider-status="disabled"]').count().then((n) => n === 1), 5000)
        && (await detail("deepseek").locator('[data-ui="ms-state"]').innerText()).includes(DS_KEY.slice(-4)),
    "A7 禁用 ⇒ 状态点变灰,末四位还在");
  // 09-24 QA-执行 K3(两家):同一屏圆点「未启用」、状态句 / 提示却写「已禁用」—— 照 ZCode 统一成一个词
  check(!/已禁用/.test(await detail("deepseek").innerText()),
    `K3 禁用后详情里不再出现「已禁用」(圆点叫「未启用」)(状态句「${await detail("deepseek").locator('[data-ui="ms-state"]').innerText()}」,提示「${await notice()}」)`);
  // 第 1 轮代码评审 DeepSeek #1(track opendesign-key-restart):未启用的那家存 key,提示不许叫他去右下角换(菜单里藏着它)
  await detail("deepseek").locator('[data-ui="ms-key"]').fill(DS_KEY);
  await detail("deepseek").locator('[data-ui="ms-key-save"]').click();
  // 先等**存 key 的那句**出来(以「已保存」开头)再判:禁用那一下的提示本来就带「未启用」,不等就会读到旧提示假绿(红检实测过)
  check(await until(async () => /^已保存/.test(await notice()), 5000)
        && /启用/.test(await notice()) && !/右下角就能换/.test(await notice()),
    `R1-1 未启用的那家存 key:提示说要先启用,不叫他去右下角换(「${await notice()}」)`);
  await backToChat();
  let tree = await menuTree();
  check(!tree.deepseek && tree.mimo?.selected, `A7/A12 禁用的那家不在换模型菜单里(实际 ${JSON.stringify(Object.keys(tree))})`);
  await page.keyboard.press("Escape");
  await openSettings("deepseek");
  await detail("deepseek").locator('[data-ui="ms-enable"]').click();
  check(await until(() => navItem("deepseek").locator('[data-provider-status="ready"]').count().then((n) => n === 1), 5000),
    "A7 再启用 ⇒ 不用重填 key 就回到就绪");
  await backToChat();
  tree = await menuTree();
  check(!!tree.deepseek && tree.mimo?.selected && !tree.deepseek.selected, "A7/A4 启用后回到菜单;勾仍只在当前那家");
  await page.keyboard.press("Escape");

  // ── 空 key(A20)──
  await openSettings("mimo");
  await detail("mimo").locator('[data-ui="ms-key-save"]').click();
  check(await until(async () => /空/.test(await notice()), 5000)
        && (await detail("mimo").locator('[data-ui="ms-state"]').innerText()).includes(MIMO_KEY.slice(-4))
        && readFileSync(join(home, ".openDesign", "key.txt"), "utf8").trim() === MIMO_KEY,
    `A20 空着保存 ⇒ 报错,原 key 与末四位不变(「${await notice()}」)`);
  // K1(09-25 track opendesign-key-restart 改写):改的就是正在用的那家(MiMo)的 key ⇒ 网关在跑、不找外壳,
  //   提示说下一句就用新 key;原来问的是「请了外壳重启、提示一直说重启」(存 key 要重启时的契约)。
  {
    const before = frames.length;
    await detail("mimo").locator('[data-ui="ms-key"]').fill(MIMO_KEY);
    await detail("mimo").locator('[data-ui="ms-key-save"]').click();
    check(await until(async () => /下一句/.test(await notice()), 5000) && !/重启|稍等/.test(await notice()),
      `K1 改正在用的那家的 key:提示说下一句就用新 key,不提重启(「${await notice()}」)`);
    await page.waitForTimeout(3500);   // > 两轮轮询:提示不许被轮询改回别的说法
    check(/下一句/.test(await notice()) && frames.length === before,
      `K1 网关在跑 ⇒ 没找外壳,提示也没被改口(实际「${await notice()}」,帧 ${JSON.stringify(frames.slice(before))})`);
  }

  // ── 添加供应商:拒收(A19 / A9)──
  const form = page.locator('[data-ui="ms-provider-form"]');
  const fillForm = async ({ name = "", baseUrl = "", key = "", models = "" }) => {
    await page.locator(`${MS} [data-ui="ms-add-provider"]`).click();
    await form.waitFor({ timeout: 5000 });
    await form.locator('[data-ui="ms-pf-name"]').fill(name);
    await form.locator('[data-ui="ms-pf-base"]').fill(baseUrl);
    await form.locator('[data-ui="ms-pf-key"]').fill(key);
    await form.locator('[data-ui="ms-pf-models"]').fill(models);
    await form.locator('[data-ui="ms-pf-save"]').click();
  };
  const customCount = () => page.locator(`${MS} [data-ui="ms-group"][data-group="custom"] [data-ui="ms-nav-item"]`).count();
  for (const [f, why] of [[{ baseUrl: VENDOR_BASE, key: CUSTOM_KEY, models: "gpt-e2e" }, "缺名称"],
                          [{ name: "本地中转", baseUrl: VENDOR_BASE, key: CUSTOM_KEY, models: "" }, "没有模型"],
                          [{ name: "冒充小米", baseUrl: CATALOG.mimo.apiBase, key: CUSTOM_KEY, models: "gpt-e2e" }, "Base URL 撞内置"]]) {
    await fillForm(f);
    const err = await until(() => form.locator('[data-ui="ms-pf-error"]').isVisible(), 5000)
      ? await form.locator('[data-ui="ms-pf-error"]').innerText() : "";
    check(err.trim().length > 0 && await customCount() === 0 && currentModel() === "mimo-e2e",
      `${why === "Base URL 撞内置" ? "A9" : "A19"} 添加供应商${why} ⇒ 说人话、不新增、当前不变(「${err.trim()}」)`);
    await page.keyboard.press("Escape");
    await until(async () => !(await form.isVisible()), 3000);
  }

  // ── 添加供应商:收下 → 不等重启就能测 → 重启后菜单能选(A10 / A15)──
  await page.locator(`${MS} [data-ui="ms-add-provider"]`).click();
  await form.waitFor({ timeout: 5000 });
  check(/Chat Completions/.test(await form.locator('[data-ui="ms-pf-format"]').innerText().catch(() => ""))
        && await form.locator('[data-ui="ms-pf-format"] select, [data-ui="ms-pf-format"] input:not([readonly])').count() === 0,
    "A10 API 格式只读:Chat Completions");
  await form.locator('[data-ui="ms-pf-name"]').fill("本地中转");
  await form.locator('[data-ui="ms-pf-base"]').fill(VENDOR_BASE);
  await form.locator('[data-ui="ms-pf-key"]').fill(CUSTOM_KEY);
  await form.locator('[data-ui="ms-pf-models"]').fill("gpt-e2e\nother-e2e");
  const framesA10 = frames.length;
  await form.locator('[data-ui="ms-pf-save"]').click();
  check(await until(async () => (await customCount()) === 1, 8000), "A10 自定义供应商出现在左栏「自定义供应商」下");
  const cid = await page.locator(`${MS} [data-ui="ms-group"][data-group="custom"] [data-ui="ms-nav-item"]`).getAttribute("data-provider");
  await select(cid);
  check(await detail(cid).locator('[data-ui="ms-key-link"]').count() === 0, "A28 自定义供应商没有「获取 API Key」链接(不画空链接)");
  await modelRow(cid, "gpt-e2e").locator('[data-ui="ms-test"]').click();
  const res = detail(cid).locator('[data-ui="ms-test-result"]');
  check(await until(async () => /成功/.test(await res.innerText()), 10000) && vendorSeen.some((v) => v.auth && v.model === "gpt-e2e"),
    `A15/A10 不等重启就能「测试」,用的是刚存的 key(「${await res.innerText().catch(() => "")}」)`);
  await modelRow(cid, "other-e2e").locator('[data-ui="ms-test"]').click();
  // 09-24 QA-执行 K2(Grok D4):只甩「404 model not found」不算可读 —— 要先说人话(模型 ID 不对),原文可留作括号
  check(await until(async () => /模型 ID/.test(await res.innerText()) && /404/.test(await res.innerText()), 10000)
        && !(await res.innerText()).includes(CUSTOM_KEY),
    `A2 测试失败给可读原因、不带 key(「${await res.innerText().catch(() => "")}」)`);
  check(await until(() => navItem(cid).locator('[data-provider-status="ready"]').count().then((n) => n === 1), 5000)
        && frames.length === framesA10,
    `A10 带 key 添加 ⇒ 网关在跑、不找外壳,当场就绪(09-25 改写;帧 ${JSON.stringify(frames.slice(framesA10))})`);
  await backToChat();
  check(await pickInMenu(cid, "gpt-e2e"), "A10 聊天框换模型里选得到自定义供应商的模型,配置真的换过去");
  const cfg = readCfg();
  const preset = cfg.model_presets[cfg.agents.defaults.modelPreset];
  check(preset && cfg.providers[preset.provider]?.apiBase === VENDOR_BASE,
    `A10 选中后发往自定义供应商的端点(预设挂在 ${preset?.provider})`);

  // ── 改名 / 改 Base URL 撞内置被拒(Q8)──
  await openSettings(cid);
  await detail(cid).locator('[data-ui="ms-name"]').fill("本地中转二号");
  await detail(cid).locator('[data-ui="ms-provider-save"]').click();
  check(await until(async () => /二号/.test(await navItem(cid).innerText()), 5000), "Q8 自定义供应商能改名");
  await detail(cid).locator('[data-ui="ms-base"]').fill(CATALOG.deepseek.apiBase);
  await detail(cid).locator('[data-ui="ms-provider-save"]').click();
  // 等的是**拒收那句话**(「这个地址已经是…」),不是随便一句提示 —— 上一步改名的「已保存」也是一句提示
  check(await until(async () => /已经是/.test(await notice()), 5000)
        && readCfg().providers[preset.provider]?.apiBase === VENDOR_BASE,
    `Q8 改 Base URL 撞内置 ⇒ 拒收,端点不变(「${await notice()}」)`);

  // ── 刷新不丢东西(A27)──
  const before = await page.locator(`${MS} [data-ui="ms-nav-item"]`).evaluateAll((els) => els.map((e) => e.getAttribute("data-provider")));
  await page.locator(`${MS} [data-ui="ms-refresh"]`).click();
  await page.waitForTimeout(800);
  const after = await page.locator(`${MS} [data-ui="ms-nav-item"]`).evaluateAll((els) => els.map((e) => e.getAttribute("data-provider")));
  await select("mimo");
  check(JSON.stringify(before) === JSON.stringify(after) && await modelRow("mimo", "mimo-e2e").count() === 1,
    "A27 刷新不丢数据");

  // ── 删掉:先换回内置,再删自己加的模型与供应商(A16)──
  await backToChat();
  check(await pickInMenu("mimo", "mimo-v2.5"), "前置:换回 mimo-v2.5");
  await page.keyboard.press("Escape");
  await openSettings("mimo");
  await modelRow("mimo", "mimo-e2e").locator('[data-ui="ms-delete"]').click();
  check(await until(async () => (await modelRow("mimo", "mimo-e2e").count()) === 0, 5000), "A16 自己加的模型删得掉");
  await select(cid);
  page.once("dialog", (d) => d.accept());
  await detail(cid).locator('[data-ui="ms-delete-provider"]').click();
  check(await until(async () => (await customCount()) === 0, 8000), "Q8 自定义供应商删得掉");
  await backToChat();
  tree = await menuTree();
  check(!tree[cid] && !(tree.mimo?.models || []).includes("mimo-e2e"), `A16 删掉的模型与供应商从换模型菜单里消失(实际 ${JSON.stringify(tree)})`);
  await page.keyboard.press("Escape");

  // ── 网关没在跑时存 key(track opendesign-key-restart):请外壳把它起起来,提示说「正在准备」不说「重启」──
  //    (不用「正在启动后台」:那是业主 09-24 让删掉的启动横幅的原话,test_quiet_start_icons q1 全仓禁用。)
  //    (全新装机第一次存 key 就是这个形状:开机没 key ⇒ 只起了工作台。)
  {
    await new Promise((r) => fakeGw.close(r));
    const before = frames.length;
    await openSettings("mimo");
    await detail("mimo").locator('[data-ui="ms-key"]').fill(MIMO_KEY);
    await detail("mimo").locator('[data-ui="ms-key-save"]').click();
    check(await until(async () => /正在准备聊天服务/.test(await notice()), 5000) && !/重启/.test(await notice()),
      `G1 网关没在跑:提示正在准备聊天服务,不提重启(「${await notice()}」)`);
    check(await until(() => frames.slice(before).includes("RESTART-BACKEND"), 5000),
      `G1 网关没在跑 ⇒ 请外壳把它起起来(帧 ${JSON.stringify(frames.slice(before))})`);
    await page.keyboard.press("Escape");
    await backToChat();
  }

  // ── 全程 key 足迹(A8)──
  const html = await page.content();
  const aria = String(await page.locator("body").ariaSnapshot().catch(() => ""));
  for (const k of KEYS) {
    for (const [where, text] of [["页面 HTML", html], ["无障碍树", aria], ["控制台", consoleLines.join("\n")],
                                 ["响应体", bodies.join("\n")], ["ds_web 日志", srvOut.join("")], ["配置文件", readFileSync(cfgPath, "utf8")]]) {
      check(!text.includes(k) && !text.includes(k.slice(0, 12)), `A8 key(…${k.slice(-4)})没出现在${where}里`);
    }
  }
  check(!consoleLines.some((l) => l.startsWith("PAGEERROR")), `全程没有页面级 JS 报错${consoleLines.find((l) => l.startsWith("PAGEERROR")) ?? ""}`);
} catch (e) {
  console.log(`  FAIL - 场景本身崩了:${e?.stack || e}`);
  failures += 1;
} finally {
  try { await browser?.close(); } catch { /* 已经关了 */ }
  try { srv?.kill("SIGKILL"); } catch { /* 已经没了 */ }
  fakeShell.close();
  fakeVendor.close();
  try { fakeGw.close(); } catch { /* 已经关了 */ }
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures ? `\n${failures} 条红` : "\n全绿");
process.exit(failures ? 1 : 0);
