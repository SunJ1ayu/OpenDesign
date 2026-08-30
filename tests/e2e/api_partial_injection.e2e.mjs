// 桥**只注入了一半**时,界面不许整页变白。主 agent 亲写。
//
// 🔴 2026-08-30 云 Windows 真机复现(run 33305829954):
//    日志里先 `frontend.frame_submitted 1028x749`(界面确实画出来了),
//    紧接着 `frontend.error Uncaught TypeError: c.window_state is not a function`,
//    而那一刻的截图是**整片空白**。机制:
//      · `WindowChrome.tsx:62` 写的是 `api()?.window_state()` —— `?.` 只挡"api 是空的",
//        挡不住"api 在、但方法还没挂上" ⇒ `undefined()` **同步抛**,后面的 .catch 接不到;
//      · pywebview 注入 api 是分步的(本项目为注入时机栽过 0.89/0.90/0.91 三次);
//      · 异常发生在 useEffect 里,而**全仓没有任何 ErrorBoundary**
//        ⇒ React 18 把整棵树卸载 ⇒ 整页白。
//
//    这条路以前是**隐形**的:没有前端错误上报,它就只是"打开全是白的,没有任何线索"。
//
// 跑法:node tests/e2e/api_partial_injection.e2e.mjs(自起 ds_web 于 8832)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8832;
const tmp = mkdtempSync(join(tmpdir(), "partialapi-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: join(tmp, "ws"), projectsDir: ".", projects: {} }));
mkdirSync(join(tmp, "ws"), { recursive: true });

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
const expect = (c, l) => { if (c) console.log(`  ok - ${l}`); else { failures++; console.error(`  FAIL: ${l}`); } };

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });

  // 🔴 只注入 report_startup,**故意不给 window_state** —— 这就是真机上那一刻的形状。
  await page.addInitScript(() => {
    window.__errs = [];
    window.addEventListener("error", (e) => window.__errs.push(String(e.message)));
    window.pywebview = { api: { report_startup() { return Promise.resolve({ accepted: true }); } } };
    setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 50);
  });

  await page.goto(`${base}/?shell=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  const size = await page.evaluate(() => {
    const r = document.getElementById("root")?.getBoundingClientRect();
    return { w: Math.round(r?.width ?? 0), h: Math.round(r?.height ?? 0),
             kids: document.getElementById("root")?.childElementCount ?? 0 };
  });
  const errs = await page.evaluate(() => window.__errs || []);
  console.log(`\n== 桥只注入一半:root ${size.w}x${size.h},子节点 ${size.kids} 个,错误 ${JSON.stringify(errs)}`);

  expect(size.kids > 0,
    `界面还在(root 有 ${size.kids} 个子节点)—— 0 个 = React 把整棵树卸载了 = 业主眼里整页白`);
  expect(!errs.some((e) => /window_state is not a function/.test(e)),
    `不许再抛 "window_state is not a function"(真机上正是它把页面打没的)`);
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
