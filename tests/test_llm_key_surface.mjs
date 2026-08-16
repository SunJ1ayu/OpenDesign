// T4 oracle 之二:**前端源码面的静态不变量**(不需要 llmKey.ts 存在就能跑)。
// 主 agent 亲写;执行腿逐字节 off-limits。track opendesign-key-onboarding。
//
// 为什么单独一个文件:这三条扫的是**源码文本**,和模块导没导得出来无关。
// 混在 test_llm_key.mjs 里时,实现还没落地 ⇒ 整份文件红在 import 上 ⇒
// **连"这三条闸自己有没有坏"都问不出来**。而一个永远红(或永远绿)的闸
// 和没有闸一样 —— 这个仓里栽过一次(win-deps-audit.py 剥后缀剥错,任何包都判缺失)。
// 拆出来之后,它们从此刻起就给真结论。
//
// 跑法:node --test tests/test_llm_key_surface.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "web", "src", "llmKey.ts");

/** web/src 下所有 .ts/.tsx(不含 dist / node_modules)。 */
function walkSrc(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name === "dist") continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkSrc(p));
    else if (/\.tsx?$/.test(e.name)) out.push(p);
  }
  return out;
}


test("b2 端点/模型值不许在**整个前端**里第二次硬编码(两边一起错时判据也一起绿)", () => {
  // 🔴 第一版只扫 llmKey.ts 一个文件 —— 那是半恒真的:把厂商端点抄进**组件**
  //    就照样全绿(我自攻时抓到的 A-1)。所以扫整棵源码树。
  //    实测过零命中,扩到全树不会误伤。
  const files = walkSrc(join(ROOT, "web", "src"));
  for (const f of files) {
    const src = readFileSync(f, "utf-8");
    // 这些值的唯一出处是出货模板 + bin/ds_credential.py 的 PROVIDERS。
    for (const v of ["api.deepseek.com", "xiaomimimo.com", "deepseek-v4", "mimo-v2"]) {
      assert.ok(!src.includes(v), `${f.slice(ROOT.length + 1)} 里抄了一份后端的值:${v}`);
    }
  }
});


/** 读 llmKey.ts;还没落地时给一句人话,别甩 ENOENT。 */
function readImpl() {
  if (!existsSync(SRC)) {
    assert.fail("web/src/llmKey.ts 还不存在 —— 实现没落地,这一条此刻问不出东西");
  }
  return readFileSync(SRC, "utf-8");
}

test("c3 逻辑层不许碰 localStorage / sessionStorage / cookie", () => {
  const src = readImpl();
  for (const v of ["localStorage", "sessionStorage", "document.cookie"]) {
    assert.ok(!src.includes(v), `llmKey.ts 里出现了 ${v} —— key 只能过一次手,不许留副本`);
  }
});

test("c4 逻辑层不许自己打日志(console 是 e2e 明账要扫的那一面)", () => {
  const src = readImpl();
  assert.ok(!/\bconsole\.(log|info|warn|error|debug)\s*\(/.test(src),
            "llmKey.ts 里有 console.* —— 调试语句是 key 最常见的漏法");
});

