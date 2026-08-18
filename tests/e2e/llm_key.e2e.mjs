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
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, existsSync, statSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8837;
const BASE = `http://127.0.0.1:${PORT}`;

// 长得像真 key、且在任何文本里都好搜的串。**全篇唯一的秘密。**
const KEY = "sk-e2e-ORACLE-0123456789abcdef-TAIL9999";
// 🔴 只对**整串**过敏的判据挡不住"部分泄漏":实现回显前 20 个字符,
//    每一条 `.includes(KEY)` 都是绿的。所以同时扫一段前缀。
//    取前 12 是安全的:后端的 hint 形态是「前4…后4」,不含前 12。
const KEY_HEAD = KEY.slice(0, 12);
// 而且不能只找原样的串:base64 一下、URL 编码一下,同样是泄漏。
const KEY_B64 = Buffer.from(KEY, "utf-8").toString("base64");
const KEY_URI = encodeURIComponent(KEY);
const FORMS = [KEY, KEY_HEAD, KEY_B64, KEY_B64.slice(0, 16), KEY_URI];
const leaked = (text) => { const t = String(text ?? ""); return FORMS.some((f) => t.includes(f)); };
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
// 🔴 这一份 e2e 跑的是**打包产物**,而静态面判据扫的是**源码** ——
//    不核对新鲜度的话,"源码里干干净净、dist 里是另一套"能骗过两边。
{
  const newest = (dir) => {
    let t = 0;
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      if (e.name === "node_modules") continue;
      const p2 = join(dir, e.name);
      t = Math.max(t, e.isDirectory() ? newest(p2) : statSync(p2).mtimeMs);
    }
    return t;
  };
  if (newest(join(ROOT, "web", "src")) > newest(dist)) {
    console.error("web/dist 比 web/src 旧 —— 先 npm run build,否则这一趟验的不是你改的那份代码");
    process.exit(1);
  }
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
    // 🔴 显式清掉配置引用的那个变量:`...process.env` 会把开发机的环境整个带进来,
    //    而 status 现在**认 env 这一层**(E 组)⇒ 开发机上恰好设了它的话,A1
    //    「没配 key 时首屏自动弹卡」就会红,而红的理由跟被测代码毫无关系。
    //    同族教训:HOME 也是这么泄进来的(08-16 那 29 条 e2e)。空串=不存在。
    MIMO_TP_KEY: "",
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
    // postData() 对二进制 body 返回 null ⇒ Blob / FormData / sendBeacon 发出去的
    // key 会整个逃掉。用 buffer 兜底。
    let post = req.postData() ?? "";
    if (!post) { try { post = (req.postDataBuffer() ?? Buffer.alloc(0)).toString("utf-8"); } catch { post = ""; } }
    const hdr = JSON.stringify(req.headers() ?? {});
    if (leaked(req.url()) || leaked(post) || leaked(hdr)) {
      requestsWithKey.push({ url: req.url(), method: req.method(),
                             inUrl: leaked(req.url()), inHeader: leaked(hdr) });
    }
  });
  page.on("response", async (res) => {
    // 头一起收:`Set-Cookie: llm_key=<KEY>` 这条路只看 body 是看不见的。
    let headers = {};
    try { headers = await res.allHeaders(); } catch { /* 拿不到就算了 */ }
    try {
      const body = await res.text();
      responses.push({ url: res.url(), body, headers: JSON.stringify(headers) });
    } catch {
      responses.push({ url: res.url(), body: "", headers: JSON.stringify(headers) });
    }
  });

  await page.goto(BASE, { waitUntil: "domcontentloaded" });

  // A —— 没配 key 时,一打开就有得填
  const card = page.locator('[data-ui="llm-key-card"]');
  await run("A1 没配 key 时首屏自己弹出填 key 的卡片", async () => {
    await card.waitFor({ timeout: 15000 });
    CARD_UP = true;
  });
  await runIfCard("A2 卡片里有厂商选择、key 输入框、保存按钮", async () => {
    // 数**看得见的**那一个:两个入口都常驻 DOM、靠 CSS 显隐,是合理实现,
    // 按总数判会把它冤枉掉。业主眼前只该有一个,这才是要守的东西。
    for (const ui of ["llm-key-provider", "llm-key-input", "llm-key-save"]) {
      const n = await page.locator(`[data-ui="${ui}"]:visible`).count();
      if (n !== 1) throw new Error(`屏幕上看得见的 [data-ui="${ui}"] 应恰好 1 个,实为 ${n}`);
    }
  });
  await runIfCard("A3 key 输入框是密码框(肩后偷看是最原始的那一面)", async () => {
    const inp = page.locator('[data-ui="llm-key-input"]');
    const t = await inp.getAttribute("type");
    if (t !== "password") throw new Error(`type=${t}`);
    // 不加 autocomplete=off,浏览器会把这把 key 记进自己的凭据库 ——
    // 那是 key.txt 之外的第二个持久副本,而且 C9 扫不到它。
    const ac = (await inp.getAttribute("autocomplete") || "").toLowerCase();
    if (ac !== "off" && ac !== "new-password") {
      throw new Error(`autocomplete=${ac || "(没设)"} —— 浏览器会记住这把 key`);
    }
  });
  await runIfCard("A4 厂商选项由后端给,后端有几家就是几家", async () => {
    // 问"每一家都在不在",不锁总数 —— 锁总数会把合理的「请选择…」占位项判成红,
    // 而误报和假绿一样坏。
    const values = await page.locator('[data-ui="llm-key-provider"] option')
      .evaluateAll((os) => os.map((o) => o.value));
    for (const id of PROVIDER_IDS) {
      if (!values.includes(id)) throw new Error(`后端有 ${id},界面选项里没有:${JSON.stringify(values)}`);
    }
  });

  // A5~A7 —— 这张卡片挡在业主和整个界面之间,所以「关得掉」「关掉不留残余」
  // 跟「弹得出来」同等重要。
  //
  // 🔴 补这三条的直接原因(2026-08-16,别把它当锦上添花删掉):T4 合入后的全量回归
  //    **29 条 e2e 一起红**,形态全是 `connect-modal-mask intercepts pointer events`
  //    —— 遮罩吃掉了所有点击。那次的根因确实在夹具(开发机没 key ⇒ 每条 e2e 一开页面
  //    就被自动弹的卡片挡住),已在 tests/e2e/run-all.sh 修掉。**但那个修法是给每条
  //    e2e 预置一把假 key,等于把「没配 key 的那个界面」从所有 e2e 的视野里挪走了**
  //    —— 而那恰恰是业主装完第一次打开时看到的界面。⇒ 挪走之后,谁哪天删掉
  //    App.tsx 里遮罩的 onClick,判据将**一条都不红**,而业主会被一张关不掉的卡片
  //    锁在门外。这三条就是补上那个洞:夹具让别的场景绕开它,这里正面问它。
  let CARD_DISMISSED = false;
  await runIfCard("A5 点卡片外面能把它关掉(业主可以先不填,先看看)", async () => {
    // 点遮罩左上角:离卡片最远,不会误点到卡片自己身上。
    await page.locator(".connect-modal-mask").click({ position: { x: 5, y: 5 } });
    await card.waitFor({ state: "hidden", timeout: 8000 });
    CARD_DISMISSED = true;
  });
  const runIfDismissed = async (label, fn) => {
    if (!CARD_DISMISSED) { failed++; console.log(`  FAIL - ${label}: 卡片(A5)就没关掉 —— 这一问此刻问不出东西,不许算绿`); return; }
    await run(label, fn);
  };
  await runIfDismissed("A6 关掉之后点得动别的东西(遮罩不许留下来吃点击)", async () => {
    // 🔴 「卡片不见了」证明不了「不挡了」:遮罩完全可以留在 DOM 里透明地继续拦点击,
    //    肉眼和 waitFor(hidden) 都看不出来 —— 上面那 29 条红正是这个形态。
    //    所以这一问必须**真点一次别的东西,并且看见它有反应**。
    await page.locator(".side-footer .side-row").click({ timeout: 5000 });
    await page.locator(".settings-pop").waitFor({ timeout: 8000 });
  });
  await run("A7 关掉不等于「以后别再提醒我」:重开页面照样弹(否则他永远填不上)", async () => {
    // 这一问还兼着**恢复现场**:B 组要用这张卡片填 key,而 A5 把它关掉了。
    // 未配置状态下重开必弹(A1 的机制)⇒ 删掉这一问会让 B 组莫名其妙全红。
    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    await card.waitFor({ timeout: 15000 });
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
    if (!/重启|重新启动|重新打开/.test(txt)) throw new Error(`没让他重启:「${txt}」`);
  });

  // B2/B3 —— 落盘落对地方(值从后端真相源来,不在这儿抄第二遍)
  await runIfSaved("B2 key 落在 key.txt 里,一行、就是原文", async () => {
    const p = join(home, ".openDesign", "key.txt");
    const got = readFileSync(p, "utf-8").trim();
    if (got !== KEY) throw new Error(`key.txt 内容对不上:${JSON.stringify(got.slice(0, 12))}…`);
  });
  await runIfSaved("B2b 落盘的地方**有且只有** key.txt(别处再写一份就等于多一个副本)", async () => {
    // design 声称的是「secret 恰好只在 key.txt 一处」——那是个全称命题,
    // 而"读一下 key.txt 对不对"证明不了它。扫整棵临时家目录树。
    const hits = [];
    const walk = (dir) => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const f = join(dir, e.name);
        if (e.isDirectory()) { walk(f); continue; }
        let body = "";
        try { body = readFileSync(f, "utf-8"); } catch { continue; }  // 二进制跳过
        if (leaked(body)) hits.push(f);
      }
    };
    walk(tmp);
    const expected = join(home, ".openDesign", "key.txt");
    const extra = hits.filter((f) => f !== expected);
    if (extra.length) throw new Error(`key 还写进了别处:${extra.join(", ")}`);
    if (!hits.includes(expected)) throw new Error("key.txt 里反而没有 —— 前提坏了");
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
    // 🔴 全称版:规格说的是「配置里不含 key」,不是「apiKey 字段里不含 key」。
    //    只挑字段验的话,塞进 notes / label / 任何新字段都全绿。逐字节扫整份文件。
    const rawCfg = readFileSync(cfgPath, "utf-8");
    if (leaked(rawCfg)) throw new Error("配置文件里出现了 key(哪怕不在 apiKey 字段上)");
  });

  // C —— 🔴 主断言:KEY 的全机器足迹
  //
  // 扫之前先静置一会儿:保存一返回就扫 = **扫得太早**,一个 500ms 之后才发出去的
  // 上报会整个漏掉,而判据全绿。这一秒半买的是"迟到的那一发也算数"。
  if (SAVED) await page.waitForTimeout(1500);
  await runIfSaved("C1 页面 HTML 里没有 key 原文", async () => {
    if (leaked(await page.content())) throw new Error("key 出现在 DOM 里");
  });
  await runIfSaved("C3 控制台一句都没漏(调试语句是最常见的漏法)", async () => {
    const hit = consoleLines.filter((l) => leaked(l));
    if (hit.length) throw new Error(`console 里有 key:${hit[0].slice(0, 80)}`);
  });
  await runIfSaved("C4 服务器回给浏览器的每一份响应体里都没有 key", async () => {
    const hit = responses.filter((r) => leaked(r.body) || leaked(r.headers));
    if (hit.length) {
      const how = leaked(hit[0].body) ? "body" : "响应头(Set-Cookie 之类)";
      throw new Error(`响应${how}带 key:${hit.map((h) => h.url).join(", ")}`);
    }
  });
  await runIfSaved("C6 ds_web 自己的日志里没有 key", async () => {
    if (leaked(srvOut.join(""))) throw new Error("服务端日志带 key");
  });
  await runIfSaved("C9 浏览器存储里没有 key(localStorage / sessionStorage / cookie / IndexedDB / Cache)", async () => {
    // 🔴 这条补的是原本整块盲区:C 组扫的是 HTML / aria / console / 响应体 /
    //    服务端日志 —— **一个前端存储都没查**。组件"顺手记一下方便下次改 key"
    //    就能全绿地把原文留在业主磁盘上。
    //    第二轮(攻题腿)又指出 cookie / IndexedDB / Cache Storage 也在盲区里,已一并扫。
    const dump = await page.evaluate(async () => {
      const out = {};
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i); out["ls:" + k] = localStorage.getItem(k);
      }
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i); out["ss:" + k] = sessionStorage.getItem(k);
      }
      out["cookie"] = document.cookie;
      out["location"] = location.href;      // pushState("#"+key) 会进地址栏、历史、后续 Referer
      out["window.name"] = window.name;     // 跨页面存活的老牌藏身处
      try {
        const dbs = (await indexedDB.databases?.()) ?? [];
        for (const { name } of dbs) {
          const db = await new Promise((res, rej) => {
            const rq = indexedDB.open(name); rq.onsuccess = () => res(rq.result); rq.onerror = () => rej();
          });
          for (const store of Array.from(db.objectStoreNames)) {
            const rows = await new Promise((res) => {
              const rq = db.transaction(store, "readonly").objectStore(store).getAll();
              rq.onsuccess = () => res(rq.result); rq.onerror = () => res([]);
            });
            out[`idb:${name}/${store}`] = JSON.stringify(rows);
          }
          db.close();
        }
      } catch (e) { out["idb:错误"] = String(e); }
      try {
        for (const name of await caches.keys()) {
          const c = await caches.open(name);
          for (const req of await c.keys()) {
            out[`cache:${name}/${req.url}`] = await (await c.match(req))?.text?.() ?? "";
          }
        }
      } catch (e) { out["cache:错误"] = String(e); }
      return JSON.stringify(out);
    });
    if (leaked(dump)) {
      const where = Object.entries(JSON.parse(dump)).filter(([, v]) => leaked(v));
      throw new Error(`key 存进了浏览器存储:${where.map(([k]) => k).join(", ")}`);
    }
  });
  await runIfSaved("C10 保存成功后输入框已清空(别让 key 一直躺在页面里)", async () => {
    // 两种都算对:① 表单还在但已清空;② 保存成功后整张卡片/表单直接卸载(更保守)。
    // 只认①会把②冤枉掉,而②恰恰是更安全的做法。
    const inp = page.locator('[data-ui="llm-key-input"]');
    if (await inp.count() === 0) return;                 // 卸载了,更好
    const v = await inp.inputValue();
    if (v !== "") throw new Error(`输入框里还留着 ${v.length} 个字符`);
  });
  // ⚠️ 顺序有意义:C2 必须跑在 C10(输入框已清空)**之后**。
  //    ariaSnapshot 连密码框的当前值都吐,B1 刚填完就扫 ⇒ 读屏树里本来就该有 key,
  //    「关闭卡片时才清空」这种同样正确的实现会被冤枉。误报会推着人去调钝报警器,
  //    那比漏报更贵 —— 所以把"该清空"单独问(C10),清空之后再问"读屏树干不干净"。
  await runIfSaved("C2 无障碍树里没有 key 原文(密码框挡得住眼睛,挡不住读屏)", async () => {
    // ⚠️ 不要用 page.accessibility.snapshot():**playwright 1.60 里它已经不存在了**,
    //    写成那样这条会红在 TypeError 上 —— 而"红在 TypeError 上等于没红检过"。
    //    探针实测:ariaSnapshot() 连 type=password 里**当前输入的值**都会吐出来,
    //    所以这条顺带盖住了"输入框没清空"那一面。
    if (leaked(await page.locator("body").ariaSnapshot())) throw new Error("key 出现在 aria 树里");
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
    // 🔴 不许用"死等 N 秒然后看它没弹"来判 —— 实现拉状态慢一点,
    //    「不弹」就变成「还没弹」,而这是假绿。
    //    正确的等法:等到**它确实已经知道自己配好了**(状态响应到达)再看。
    const got = page.waitForResponse(
      (r) => r.url().endsWith("/api/llm/credential") && r.status() === 200,
      { timeout: 15000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await got;                       // 状态已经到手
    await page.waitForTimeout(1200); // 再给它足够时间"弹"(要弹早弹了)
    if (await card.isVisible().catch(() => false)) throw new Error("配好了还弹");
  });
  await runIfSaved("E2 状态接口只回末四位提示,永不回原文", async () => {
    const d = await (await fetch(`${BASE}/api/llm/credential`)).json();
    if (d.configured !== true) throw new Error(`configured=${d.configured}`);
    if (leaked(JSON.stringify(d))) throw new Error("状态接口把 key 回显了");
    if (!d.hint || !String(d.hint).includes(KEY.slice(-4))) {
      throw new Error(`hint 认不出是哪把:${d.hint}`);
    }
    // 「不含整串」不等于「没泄漏」:回显前 20 个字符同样是泄漏。钉死它的规模。
    if (leaked(d.hint) || String(d.hint).length > 16) {
      throw new Error(`hint 给多了(${String(d.hint).length} 字符):${d.hint}`);
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
    // 文本节点 or placeholder 都算"显示了" —— 只认 innerText 会把
    // 「placeholder 里写末四位」这种合理实现判红(误报)。
    const txt = await card.innerText();
    const aria = String(await card.ariaSnapshot());
    const shown = txt + "\n" + aria;
    if (!shown.includes(KEY.slice(-4))) {
      throw new Error(`卡片没显示末四位:「${txt.slice(0, 120)}」`);
    }
    if (shown.includes(KEY)) throw new Error("卡片把 key 原文显示出来了");
  });
  // G —— 换一把 key 再存一次(原来只问了"第一次填")
  await runIfSaved("G1 换 key:key.txt 被**覆盖**,旧的那把不许留在里面", async () => {
    const KEY2 = "sk-e2e-SECOND-abcdefghijklmn-TAIL0002";
    await page.locator('[data-ui="llm-key-input"]').fill(KEY2);
    await page.locator('[data-ui="llm-key-save"]').click();
    await page.waitForTimeout(1200);
    const body = readFileSync(join(home, ".openDesign", "key.txt"), "utf-8");
    if (body.includes(KEY)) throw new Error("旧 key 还在文件里 —— 是追加不是覆盖");
    if (body.trim() !== KEY2) throw new Error(`换完之后内容不对:${JSON.stringify(body.slice(0, 20))}…`);
    if (body.trim().split("\n").length !== 1) throw new Error("key.txt 变成多行了");
  });
  // C5 故意排在最后:`pagehide` / `visibilitychange` / 卸载时才发的 beacon,
  //     在 C 组那个时点根本还没发生。E1 的 reload 会真正触发一次卸载,
  //     所以要等它之后再清点"这一整趟里到底有多少东西带着 key 飞出去过"。
  // H —— key 由环境变量供着时,这一格必须**提前**变成只读
  //
  // 对照 DeepSeek Harness 的 credentials seam:`describe()` 把「由当前进程环境供值」
  // 的引用报成 `writable: false`,**界面据此提前渲染为只读**。我们的后端已经会拒绝
  // 这种写入(E 组),但那是业主填完、点了保存才撞上的 —— 那一次白填本可以避免。
  //
  // 这一问用接口 stub 造场景:后端算得对不对由 tests/test_credential.py 的 E 组管
  // (还过了红检),这里只问「前端拿到 writable=false 之后长什么样」。分工别混。
  await run("H1 key 由环境变量供着 ⇒ 输入框只读,并说清为什么", async () => {
    await page.route("**/api/llm/credential", async (route) => {
      if (route.request().method() !== "GET") { await route.continue(); return; }
      const res = await route.fetch();
      const body = await res.json();
      await route.fulfill({ json: { ...body, configured: true, source: "env",
                                    writable: false, hint: "sk-e…ENV9" } });
    });
    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    // configured=true ⇒ 不会自动弹,从设置里打开
    await page.locator(".side-footer .side-row").click();
    await page.locator('[data-ui="settings-llm-key"]').click();
    await card.waitFor({ timeout: 8000 });
    if (await page.locator('[data-ui="llm-key-input"]').isEnabled()) {
      throw new Error("被环境变量遮蔽,输入框却还能填 —— 业主会白填一次才被后端拒绝");
    }
    const shown = (await card.innerText()) + "\n" + String(await card.ariaSnapshot());
    if (!shown.includes("环境变量")) {
      throw new Error(`没告诉业主为什么改不了:「${(await card.innerText()).slice(0, 140)}」`);
    }
  });

  await runIfSaved("C5 出站带 key 的请求:每一条都必须是那次保存,且不在 URL / 头里", async () => {
    // 不锁"恰好一条"——失败重试一次是合理实现,契约里也没禁。要守的是两件:
    //   ① 真的发生过(否则这一问在空转);② **每一条**都得是那个保存请求。
    if (requestsWithKey.length === 0) throw new Error("一条带 key 的请求都没有 —— 保存根本没发出去");
    for (const r of requestsWithKey) {
      if (r.method !== "POST" || !r.url.endsWith("/api/llm/credential")) {
        throw new Error(`key 被发去了别处:${r.method} ${r.url}`);
      }
      if (r.inUrl) throw new Error("key 进了 URL(会落进 access log / 浏览器历史)");
      if (r.inHeader) throw new Error("key 进了请求头");
    }
  });
} catch (e) {
  fail("流程本身", e);
} finally {
  if (browser) await browser.close().catch(() => {});
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });   // 收摊,别留给 /tmp
}

console.log(failed === 0 ? "\nllm_key e2e: 全绿" : `\nllm_key e2e: ${failed} 条红`);
process.exit(failed === 0 ? 0 : 1);
