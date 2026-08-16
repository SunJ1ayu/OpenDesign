// T4 oracle:业主在界面里填大模型 key(真 chromium + 真 ds_web)。
// 主 agent 亲写;执行腿对本文件逐字节 off-limits。
// track opendesign-key-onboarding,design.md 第二/三节 + 「这个 oracle 能被什么骗过」。
//
// ── 为什么必须有这一条(纯逻辑判据顶不了)────────────────────────────────
// key 是**凭据**。它会不会漏,漏在浏览器那一侧:页面 HTML、无障碍树、控制台、
// 以及**线上真正飞过去的字节**。tests/test_llm_key.mjs 只能问"我写的那条路对不对";
// 它答不了"有没有从我没想到的那面漏出去"(design 骗法一)。
// 所以这里的主断言不是"功能好了",是:**整个流程走完,KEY 原文在全机器上只该出现
// 在两个地方 —— 那一次 POST 的请求体,和 key.txt。别处一次都不许。**
//
// 覆盖:
//   A 没配 key 时,一打开就有得填(不是一句"请去找记事本")
//   B 厂商是后端说了算,选谁就落谁的端点(期望值从 bin/ds_credential.py 现读,不抄)
//   C 🔴 KEY 只在"那一次 POST 的 body"和 key.txt 里出现;
//     HTML / aria / console / 任何一份响应体 / ds_web 自己的日志 / 配置文件 —— 零命中
//   D 没有外壳时那句话不许撒谎:必须叫业主自己重启(restart=manual)
//   E 存完再打开:不弹了、只显示末四位、原文永不回显
//   F 设置里能再打开**同一个**卡片(一份代码两个入口)
//
// 跑法:node tests/e2e/llm_key.e2e.mjs(自起 ds_web 于 8837;需要 web/dist 是新的)
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8837;
const BASE = `http://127.0.0.1:${PORT}`;

// 长得像真 key、且在任何文本里都好搜的串。**全篇唯一的秘密。**
const KEY = "sk-e2e-ORACLE-0123456789abcdef-TAIL9999";
const PASSWORD = "pw-only-on-the-server-side";   // 业主永远不该看见它(T2 代签)

// ---- 夹具:一份干净的假家 + 一份真结构的 nanobot 配置 ----------------------

const tmp = mkdtempSync(join(tmpdir(), "llmkey-e2e-"));
const home = join(tmp, "UserData");              // ds_web 从 HOME 找 .openDesign/key.txt
const dsRoot = join(tmp, "ds");
mkdirSync(join(home, ".nanobot"), { recursive: true });
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

const cfgPath = join(home, ".nanobot", "config.json");
// 变量名故意用 MIMO_TP_KEY(Linux 那份模板的名字),盯着"变量名从配置读、不许写死"
// 那条不变量:写死 DS_LLM_KEY 的实现在这儿会把配置改坏。
writeFileSync(cfgPath, JSON.stringify({
  channels: { websocket: { enabled: true, token: PASSWORD } },
  providers: { custom: { apiKey: "${MIMO_TP_KEY}", apiBase: "https://旧端点/v1" } },
  model_presets: {}, agents: { defaults: {} },
}, null, 2));

const dist = join(ROOT, "web", "dist");
if (!existsSync(join(dist, "index.html"))) {
  console.error("web/dist 里没有 index.html —— 先 npm run build(dist 新鲜度闸也管这个)");
  process.exit(1);
}

// 期望值的**唯一出处**是后端的 PROVIDERS(骗法四:两边各抄一份就会一起错)。
const provRaw = spawnSync("python3", ["-c", `
import sys, json; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
print(json.dumps(ds_credential.PROVIDERS, ensure_ascii=False))
`], { encoding: "utf-8" });
const PROVIDERS = JSON.parse(provRaw.stdout || "{}");
const PROVIDER_IDS = Object.keys(PROVIDERS);
if (PROVIDER_IDS.length < 2) {
  console.error("读不到后端 PROVIDERS:", provRaw.stdout, provRaw.stderr);
  process.exit(1);
}
// 挑**非默认**的那一家来验"选择真的生效"(选默认项时,不落盘也看着像对的)。
const PICK = PROVIDER_IDS[1];
const PICK_BASE = PROVIDERS[PICK].apiBase;
const PICK_MODEL = PROVIDERS[PICK].model;

// ---- 起真 ds_web,把它自己的输出也收进来(日志同样是要扫的一面)-----------

const srvOut = [];
const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: {
    ...process.env,
    HOME: home, USERPROFILE: home,
    DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT),
    DS_NANOBOT_CONFIG: cfgPath,
    DS_WEB_DIST: dist,
    // 外壳不在场 ⇒ 重启桥必然走 manual 那条路(D 就是冲它来的)
    DS_SHELL_LOCK_PORT: "",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
srv.stdout.on("data", (b) => srvOut.push(String(b)));
srv.stderr.on("data", (b) => srvOut.push(String(b)));

let failed = 0;
const fail = (label, err) => { failed++; console.log(`  FAIL - ${label}: ${err?.message ?? err}`); };

// 总闸:判据自己不许挂死。挂死的判据 = 半截收据(看起来像还在跑,其实什么都没答)
// + 一个占着端口的野进程,两样都在这个 track 里栽过。
const WATCHDOG = setTimeout(() => {
  console.log(`\n  FAIL - 判据自己超时(${180}s):没跑完就没有结论,别当它是绿的`);
  try { srv.kill("SIGKILL"); } catch { /* 已经没了 */ }
  process.exit(1);
}, 180_000);
WATCHDOG.unref();

async function waitServer(timeout = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    try {
      const r = await fetch(`${BASE}/api/health`);
      if (r.ok) return;
    } catch { /* 还没起来 */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("ds_web 20 秒没起来");
}

const run = async (label, fn) => { try { await fn(); check(true, label); } catch (e) { fail(label, e); } };

// 卡片没出来的时候,后面每一问都会各自等到超时 —— 那样跑一遍要好几分钟,
// 而且屏幕上全是"Timeout",**真正的病因(卡片压根没有)被淹掉**。
// ⇒ 显式分流:CARD_UP 不成立时后续直接判红并说清是哪一种病,不再傻等。
// (同源教训:判据里凡是"后续问依赖前面某问成立"的,必须显式分流,不能靠巧合。)
let CARD_UP = false;
const runIfCard = async (label, fn) => {
  if (!CARD_UP) { failed++; console.log(`  FAIL - ${label}: 跳过等待 —— 卡片(A1)就没出现,先修那个`); return; }
  await run(label, fn);
};

// 🔴 第二道分流,而且它防的是**假绿**,比上面那道重要得多:
// C 组问的是"key 有没有从别的面漏出去"。要是 key 压根没被送出去过(卡片没做出来、
// 保存没成功),C 组会**全绿** —— 一份根本没实现的代码拿到满分收据。
// ⇒ 凡是"没有发生坏事"型的断言,必须先证明"好事真的发生过"。
let SAVED = false;
const runIfSaved = async (label, fn) => {
  if (!SAVED) { failed++; console.log(`  FAIL - ${label}: 保存(B1)就没成功 —— 这一问此刻问不出东西,不许算绿`); return; }
  await run(label, fn);
};

// ---- 主流程 ---------------------------------------------------------------

let browser;
try {
  await waitServer();
  browser = await launchBrowser();
  const ctx = await browser.newContext();
  ctx.setDefaultTimeout(10_000);   // 默认 30s ×十几问 = 一遍红检跑到天黑
  const page = await ctx.newPage();

  // 三面监听:控制台、页面异常、**线上真正飞过的字节**(design 差异 #4)。
  const consoleLines = [];
  const pageErrors = [];
  const responses = [];      // {url, body}
  const requestsWithKey = []; // 出站里带 KEY 的,期望恰好 1 条
  page.on("console", (m) => consoleLines.push(`${m.type()}: ${m.text()}`));
  page.on("pageerror", (e) => pageErrors.push(String(e)));
  page.on("request", (req) => {
    const post = req.postData() ?? "";
    const hdr = JSON.stringify(req.headers() ?? {});
    if (req.url().includes(KEY) || post.includes(KEY) || hdr.includes(KEY)) {
      requestsWithKey.push({ url: req.url(), method: req.method(),
                             inUrl: req.url().includes(KEY), inHeader: hdr.includes(KEY) });
    }
  });
  page.on("response", async (res) => {
    try {
      const body = await res.text();
      responses.push({ url: res.url(), body });
    } catch { /* 重定向/无体,忽略 */ }
  });

  await page.goto(BASE, { waitUntil: "domcontentloaded" });

  // A —— 没配 key 时,一打开就有得填
  const card = page.locator('[data-ui="llm-key-card"]');
  await run("A1 没配 key 时首屏自己弹出填 key 的卡片", async () => {
    await card.waitFor({ timeout: 15000 });
    CARD_UP = true;
  });
  await runIfCard("A2 卡片里有厂商选择、key 输入框、保存按钮", async () => {
    for (const ui of ["llm-key-provider", "llm-key-input", "llm-key-save"]) {
      const n = await page.locator(`[data-ui="${ui}"]`).count();
      if (n !== 1) throw new Error(`[data-ui="${ui}"] 应恰好 1 个,实为 ${n}`);
    }
  });
  await runIfCard("A3 key 输入框是密码框(肩后偷看是最原始的那一面)", async () => {
    const t = await page.locator('[data-ui="llm-key-input"]').getAttribute("type");
    if (t !== "password") throw new Error(`type=${t}`);
  });
  await runIfCard("A4 厂商选项由后端给,后端有几家就是几家", async () => {
    const opts = await page.locator('[data-ui="llm-key-provider"] option').count();
    if (opts !== PROVIDER_IDS.length) {
      throw new Error(`后端 ${PROVIDER_IDS.length} 家,界面 ${opts} 个选项`);
    }
  });

  // B/D —— 填一把 key、挑非默认厂商、保存
  await runIfCard("B1 选厂商 + 填 key + 保存,界面给出结果", async () => {
    await page.locator('[data-ui="llm-key-provider"]').selectOption(PICK);
    await page.locator('[data-ui="llm-key-input"]').fill(KEY);
    await page.locator('[data-ui="llm-key-save"]').click();
    await page.locator('[data-ui="llm-key-notice"]').waitFor({ timeout: 15000 });
    SAVED = true;
  });
  await runIfSaved("D1 没有外壳 ⇒ 那句话必须叫业主自己重启,不许假装已生效", async () => {
    const txt = (await page.locator('[data-ui="llm-key-notice"]').innerText()).trim();
    if (!txt.includes("重启")) throw new Error(`没让他重启:「${txt}」`);
  });

  // B2/B3 —— 落盘落对地方(值从后端真相源来,不在这儿抄第二遍)
  await runIfSaved("B2 key 落在 key.txt 里,一行、就是原文", async () => {
    const p = join(home, ".openDesign", "key.txt");
    const got = readFileSync(p, "utf-8").trim();
    if (got !== KEY) throw new Error(`key.txt 内容对不上:${JSON.stringify(got.slice(0, 12))}…`);
  });
  await runIfSaved("B3 选中的厂商落进配置(端点+模型),而 apiKey 仍只是 ${变量} 引用", async () => {
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    const custom = cfg.providers?.custom ?? {};
    if (custom.apiBase !== PICK_BASE) throw new Error(`apiBase=${custom.apiBase},应为 ${PICK_BASE}`);
    if (custom.apiKey !== "${MIMO_TP_KEY}") {
      throw new Error(`apiKey 变了:${custom.apiKey} —— 变量名必须从配置读,不许写死`);
    }
    const preset = cfg.agents?.defaults?.modelPreset;
    if (preset !== PICK_MODEL) throw new Error(`默认模型=${preset},应为 ${PICK_MODEL}`);
  });

  // C —— 🔴 主断言:KEY 的全机器足迹
  await runIfSaved("C1 页面 HTML 里没有 key 原文", async () => {
    const html = await page.content();
    if (html.includes(KEY)) throw new Error("key 出现在 DOM 里");
  });
  await runIfSaved("C2 无障碍树里没有 key 原文(密码框挡得住眼睛,挡不住读屏)", async () => {
    const snap = await page.accessibility.snapshot({ interestingOnly: false });
    if (JSON.stringify(snap ?? {}).includes(KEY)) throw new Error("key 出现在 aria 树里");
  });
  await runIfSaved("C3 控制台一句都没漏(调试语句是最常见的漏法)", async () => {
    const hit = consoleLines.filter((l) => l.includes(KEY));
    if (hit.length) throw new Error(`console 里有 key:${hit[0].slice(0, 80)}`);
  });
  await runIfSaved("C4 服务器回给浏览器的每一份响应体里都没有 key", async () => {
    const hit = responses.filter((r) => r.body.includes(KEY));
    if (hit.length) throw new Error(`响应体带 key:${hit.map((h) => h.url).join(", ")}`);
  });
  await runIfSaved("C5 出站带 key 的请求**恰好一条**,就是那次保存;且不在 URL / 头里", async () => {
    if (requestsWithKey.length !== 1) {
      throw new Error(`带 key 的出站请求 ${requestsWithKey.length} 条:`
        + JSON.stringify(requestsWithKey.map((r) => `${r.method} ${r.url}`)));
    }
    const only = requestsWithKey[0];
    if (only.method !== "POST" || !only.url.endsWith("/api/llm/credential")) {
      throw new Error(`带 key 的那条不是保存请求:${only.method} ${only.url}`);
    }
    if (only.inUrl) throw new Error("key 进了 URL(会落进 access log / 浏览器历史)");
    if (only.inHeader) throw new Error("key 进了请求头");
  });
  await runIfSaved("C6 ds_web 自己的日志里没有 key", async () => {
    const log = srvOut.join("");
    if (log.includes(KEY)) throw new Error("服务端日志带 key");
  });
  await run("C7 页面上也不许出现网关口令(T2 拿掉手输之后,它更不该露面)", async () => {
    const html = await page.content();
    const inResp = responses.filter((r) => r.body.includes(PASSWORD));
    if (html.includes(PASSWORD)) throw new Error("口令出现在页面里");
    if (inResp.length) throw new Error(`口令回给了浏览器:${inResp[0].url}`);
  });
  await run("C8 页面没抛异常(白屏也是一种「没漏」,但那不叫做完了)", async () => {
    if (pageErrors.length) throw new Error(pageErrors[0].slice(0, 200));
  });

  // E —— 存完之后再打开
  await runIfSaved("E1 已配置时不再自己弹卡片(别打扰他)", async () => {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    if (await card.count() > 0) throw new Error("配好了还弹");
  });
  await runIfSaved("E2 状态接口只回末四位提示,永不回原文", async () => {
    const d = await (await fetch(`${BASE}/api/llm/credential`)).json();
    if (d.configured !== true) throw new Error(`configured=${d.configured}`);
    if (JSON.stringify(d).includes(KEY)) throw new Error("状态接口把 key 回显了");
    if (!d.hint || !String(d.hint).includes(KEY.slice(-4))) {
      throw new Error(`hint 认不出是哪把:${d.hint}`);
    }
  });

  // F —— 一份代码两个入口
  //
  // 🔴 先把设置弹层真的打开,再问里面有什么。第一版我漏了这一步,于是 F3
  //    「设置里没有教人敲命令行的提示」**绿了** —— 弹层压根没渲染,搜不到字符串
  //    当然"没有"。这就是上面 runIfSaved 那段说的同一种假绿,我自己又踩了一次:
  //    **"没找到坏东西"必须先证明"我真的在看那个地方"。**
  let POP_UP = false;
  await run("F0 设置弹层能打开(下面两问的前提,不许靠它没渲染来蒙混过关)", async () => {
    await page.locator(".side-footer .side-row").click();
    await page.locator(".settings-pop").waitFor({ timeout: 8000 });
    POP_UP = true;
  });
  const runIfPop = async (label, fn) => {
    if (!POP_UP) { failed++; console.log(`  FAIL - ${label}: 设置弹层(F0)没打开 —— 这一问此刻问不出东西,不许算绿`); return; }
    await run(label, fn);
  };
  await runIfPop("F1 设置里有且只有一个改 key 的入口", async () => {
    const n = await page.locator('[data-ui="settings-llm-key"]').count();
    if (n !== 1) throw new Error(`设置里的 key 入口 ${n} 个(要一处,别新增一行还留着旧的)`);
  });
  await runIfPop("F3 设置里那一行不再教业主去敲命令行", async () => {
    const html = await page.content();
    if (html.includes("set_model.py")) {
      throw new Error("旧的「跑个命令切模型」提示还在 —— 业主要的是在设置里统一弄");
    }
  });
  await runIfSaved("F2 点它打开的是同一个卡片(不是另做一份)", async () => {
    await page.locator('[data-ui="settings-llm-key"]').click();
    await card.waitFor({ timeout: 8000 });
    // 已配置时进来必须能看见"当前是哪把",否则业主不知道自己在改什么
    const txt = await card.innerText();
    if (!txt.includes(KEY.slice(-4))) throw new Error(`卡片没显示末四位:「${txt.slice(0, 120)}」`);
    if (txt.includes(KEY)) throw new Error("卡片把 key 原文显示出来了");
  });
} catch (e) {
  fail("流程本身", e);
} finally {
  if (browser) await browser.close().catch(() => {});
  srv.kill("SIGTERM");
}

console.log(failed === 0 ? "\nllm_key e2e: 全绿" : `\nllm_key e2e: ${failed} 条红`);
process.exit(failed === 0 ? 0 : 1);
