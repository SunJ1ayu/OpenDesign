// 启动不挂字 + 侧栏换 ZCode 同款线条图标(track opendesign-quiet-start-icons;主 agent 亲写,判据先单独 commit)。
// 跑法:node --test tests/test_quiet_start_icons.mjs
//
// 业主 09-23:「头上竟然显示正在启动后台还有一段话..这种东西肯定不能显示出来」;
// 侧栏 ✳⌕◎✦◷⚙ 是文字符号(Windows 上各字体粗细大小不齐)⇒「换成zcode的吧」= lucide 细线图标。
// 真渲染(图标画没画出来、大小颜色对不对)静态判不了 —— 靠 verify 里的截图。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (p) => readFileSync(path.join(ROOT, p), "utf8");

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = path.join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|css)$/.test(n)) out.push(p);
  }
  return out;
}

// lucide-static 1.47.0 原文(ISC),逐字抄自 https://cdn.jsdelivr.net/npm/lucide-static@1.47.0/icons/<name>.svg
const LUCIDE = {
  "message-circle-plus": [
    '<path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719" />',
    '<path d="M8 12h8" />',
    '<path d="M12 8v8" />',
  ],
  search: ['<path d="m21 21-4.34-4.34" />', '<circle cx="11" cy="11" r="8" />'],
  "list-todo": [
    '<path d="M13 5h8" />', '<path d="M13 12h8" />', '<path d="M13 19h8" />',
    '<path d="m3 17 2 2 4-4" />', '<rect x="3" y="4" width="6" height="6" rx="1" />',
  ],
  blocks: [
    '<path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2" />',
    '<rect x="14" y="2" width="8" height="8" rx="1" />',
  ],
  settings: [
    '<path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915" />',
    '<circle cx="12" cy="12" r="3" />',
  ],
  loader: [
    '<path d="M12 2v4" />', '<path d="m16.2 7.8 2.9-2.9" />', '<path d="M18 12h4" />',
    '<path d="m16.2 16.2 2.9 2.9" />', '<path d="M12 18v4" />', '<path d="m4.9 19.1 2.9-2.9" />',
    '<path d="M2 12h4" />', '<path d="m4.9 4.9 2.9 2.9" />',
  ],
};

// 侧栏哪一行用哪个图标(ZCode:新建 MessageCirclePlus / 搜索 Search / 插件 Blocks / 设置 Settings;待办 ZCode 没有,取 ListTodo)
const ROWS = [
  ["新对话", "message-circle-plus"],
  ["搜索", "search"],
  ["待办事项", "list-todo"],
  ["技能", "blocks"],
  ["设置", "settings"],
];

// ── 启动不挂字 ─────────────────────────────────────────────────────
test("q1 🔴 界面里没有「正在启动后台」横幅:App 不渲染、不引用,整个 web/src 找不到那句话", () => {
  const app = read("web/src/App.tsx");
  assert.doesNotMatch(app, /backend-connecting/, "横幅元素还在");
  assert.doesNotMatch(app, /backendBanner|backendState"/, "还在引横幅逻辑");
  assert.ok(!existsSync(path.join(ROOT, "web/src/backendState.ts")), "backendState.ts 只为横幅存在,该删");
  for (const f of walk(path.join(ROOT, "web/src"))) {
    const s = readFileSync(f, "utf8");
    assert.doesNotMatch(s, /正在启动后台/, `${path.relative(ROOT, f)} 还有这句话`);
    assert.doesNotMatch(s, /\.backend-banner/, `${path.relative(ROOT, f)} 还留着横幅样式`);
  }
});

// ── 侧栏图标 ──────────────────────────────────────────────────────
test("q2 🔴 侧栏五行各用对应的 lucide 线条图标,不再有 ✳⌕◎✦◷⚙ 文字符号", () => {
  const side = read("web/src/workspace/Sidebar.tsx");
  for (const ch of ["✳", "⌕", "◎", "✦", "◷", "⚙"]) {
    assert.ok(!side.includes(ch), `侧栏还有文字符号 ${ch}`);
  }
  for (const [label, icon] of ROWS) {
    // 该行按钮从 <button 起到 </button> 止,里面要同时有标签与图标
    const at = side.indexOf(`<span className="grow">${label}</span>`);
    assert.ok(at >= 0, `找不到「${label}」那一行`);
    const start = side.lastIndexOf("<button", at);
    const end = side.indexOf("</button>", at);
    const block = side.slice(start, end);
    assert.match(block, new RegExp(`<SideIcon name="${icon}"\\s*/>`), `「${label}」那一行没用 ${icon}`);
  }
});

test("q3 🔴 icons.tsx 五个图标与 lucide 1.47.0 原文逐字一致,线条色跟文字走,带 ISC 许可", () => {
  const src = read("web/src/workspace/icons.tsx");
  assert.match(src, /ISC/, "缺许可头");
  assert.match(src, /Lucide/, "许可头要写明出处");
  assert.match(src, /stroke="currentColor"/);
  assert.match(src, /strokeWidth=\{?"?2"?\}?/);
  assert.match(src, /fill="none"/);
  assert.match(src, /viewBox="0 0 24 24"/);
  for (const [name, parts] of Object.entries(LUCIDE)) {
    const at = src.indexOf(`"${name}":`);
    assert.ok(at >= 0, `icons.tsx 没有 ${name}`);
    // 取到下一个图标键(或文件尾)为止
    const rest = src.slice(at + 1);
    const nextKey = rest.search(/\n\s*"[a-z-]+":/);
    const block = nextKey >= 0 ? rest.slice(0, nextKey) : rest;
    for (const p of parts) assert.ok(block.includes(p), `${name} 缺/抄错 ${p}`);
  }
});

test("q4 历史对话行前不再有图标位(ZCode 任务行前无图标)", () => {
  const side = read("web/src/workspace/Sidebar.tsx");
  const at = side.indexOf('className="hist-row"');
  assert.ok(at >= 0);
  const block = side.slice(at, side.indexOf("</button>", at));
  assert.doesNotMatch(block, /className="ico/, "历史行还有前置图标位");
});
