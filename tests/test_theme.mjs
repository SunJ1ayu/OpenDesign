// 外观:默认深色(照 ZCode Zai Dark)+ 浅色(原暖纸面)+ 跟随系统。
// 判据只问"两套主题各自完整、组件里没有写死颜色、开机第一帧就对",不问具体色值(色值是设计,不是契约)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  applyTheme, loadThemePref, parseThemePref, resolveTheme, THEME_DEFAULT, THEME_KEY,
} from "../web/src/theme.ts";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const CSS = read("web/src/app.css").replace(/\/\*[\s\S]*?\*\//g, "");

/** 取某个选择器块里的 { 变量名: 值 }。 */
function tokens(selector) {
  const i = CSS.indexOf(`${selector} {`);
  assert.ok(i >= 0, `找不到 ${selector}`);
  const body = CSS.slice(i, CSS.indexOf("\n}", i));
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
}
const DARK = tokens(":root");
const LIGHT = tokens(':root[data-theme="light"]');
// 两个主题块之后的全部样式 = "组件"
const COMPONENTS = CSS.slice(CSS.indexOf("* { box-sizing: border-box; }"));

test("t1 偏好解析:默认深色;认不出的值回到深色;跟随系统按系统解析", () => {
  assert.equal(THEME_DEFAULT, "dark");
  assert.equal(parseThemePref(null), "dark");
  assert.equal(parseThemePref("purple"), "dark");
  assert.equal(parseThemePref("light"), "light");
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");
  assert.equal(resolveTheme("light", true), "light");
});

test("t2 applyTheme:记住偏好并把解析结果写到 <html data-theme>;存储坏了也不崩", () => {
  const store = new Map();
  const attrs = {};
  const w = {
    localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) },
    matchMedia: () => ({ matches: false }),
    document: { documentElement: { setAttribute: (k, v) => { attrs[k] = v; } } },
  };
  assert.equal(applyTheme("system", w), "light");
  assert.equal(attrs["data-theme"], "light");
  assert.equal(store.get(THEME_KEY), "system");
  assert.equal(loadThemePref(w), "system");
  const broken = { localStorage: { getItem() { throw new Error("x"); }, setItem() { throw new Error("x"); } },
                   document: w.document };
  assert.equal(loadThemePref(broken), "dark");
  assert.equal(applyTheme("light", broken), "light");
});

test("t3 🔴 两套主题变量一一对应:深色有的浅色都有,反之亦然(少一个就是某处在另一套里没颜色)", () => {
  const onlyDark = Object.keys(DARK).filter((k) => !(k in LIGHT) && !/^--(font|hover-ease)/.test(k));
  const onlyLight = Object.keys(LIGHT).filter((k) => !(k in DARK));
  assert.deepEqual(onlyDark, [], `浅色缺:${onlyDark}`);
  assert.deepEqual(onlyLight, [], `深色缺:${onlyLight}`);
});

test("t4 🔴 组件里用到的颜色变量都有定义(拼错 / 忘了加 = 两套主题下都没颜色)", () => {
  const used = new Set([...COMPONENTS.matchAll(/var\((--[\w-]+)\)/g)].map((m) => m[1]));
  const local = new Set([...COMPONENTS.matchAll(/(--[\w-]+):/g)].map((m) => m[1]));   // 组件自己定义的局部变量
  // var(--x, 兜底) 那种带兜底的不算(上面的正则只抓无兜底的 var(--x))
  const missing = [...used].filter((v) => !(v in DARK) && !local.has(v));
  assert.deepEqual(missing, [], `没定义:${missing}`);
});

test("t5 🔴 组件里不写死浅色系颜色:白底 / 白字 / 暖纸色都得走变量(否则深色下一块刺眼的白)", () => {
  const bad = [];
  for (const [n, line] of COMPONENTS.split("\n").entries()) {
    if (/#fff\b|#ffffff\b|(?<![-\w])white(?![-\w])/i.test(line)) bad.push(`${n}: ${line.trim()}`);
    // 暖纸面的那一族(#f0ede4 / #f9f7f1 / #e8e4d8 …):R、G、B 都 ≥ 0xd0 的浅色十六进制
    for (const m of line.matchAll(/#([0-9a-f]{6})\b/gi)) {
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
      if (Math.min(r, g, b) >= 0xd0 && m[1].toLowerCase() !== "f3ede2") bad.push(`${n}: ${line.trim()}`);
    }
  }
  assert.deepEqual(bad, []);
});

test("t6 开机第一帧就是对的主题:index.html 的内联脚本与 theme.ts 同一个键、同一个默认", () => {
  const html = read("web/index.html");
  const script = html.slice(html.indexOf("<script>"), html.indexOf("</script>"));
  assert.ok(script.includes(`localStorage.getItem("${THEME_KEY}")`), "键对不上");
  assert.match(script, /\|\| "dark"/, "默认不是深色");
  assert.ok(html.indexOf("<script>") < html.indexOf('src="/src/main.tsx"'), "得在应用脚本之前");
  // 桌面窗口的底色 = 深色页面底,开窗那一下不闪白
  const main = read("desktop/main.js");
  assert.ok(main.includes(`backgroundColor: "${DARK["--paper"]}"`), "窗口底色与深色 --paper 不一致");
});

test("t7 设置页图标照 ZCode:返回 ArrowLeft / 常规 Settings2 / 模型 Package;外观三档 Moon / Sun / Monitor", () => {
  const sp = read("web/src/settings/SettingsPage.tsx");
  for (const n of ["arrow-left", "settings-2", "package"]) assert.ok(sp.includes(`<SideIcon name="${n}" />`), n);
  for (const n of ["moon", "sun", "monitor"]) assert.ok(sp.includes(`icon: "${n}"`), n);
  assert.doesNotMatch(sp, /function Icon\(/, "自己手画的那套图标该删了");
  assert.doesNotMatch(sp, /深色即将支持/);
  // lucide-static 1.47.0 原文(ISC)逐字
  const icons = read("web/src/workspace/icons.tsx");
  for (const frag of [
    '<path d="m12 19-7-7 7-7" />',
    '<circle cx="17" cy="17" r="3" />',
    '<polyline points="3.29 7 12 12 20.71 7" />',
    '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401" />',
    '<path d="m19.07 4.93-1.41 1.41" />',
    '<rect width="20" height="14" x="2" y="3" rx="2" />',
  ]) assert.ok(icons.includes(frag), frag);
});

test("t8 圆角照 ZCode 的档位:只用 4 / 6 / 8 / 12 / 16 px(外加胶囊与圆)", () => {
  const odd = [...COMPONENTS.matchAll(/border-radius:\s*([^;}]+)/g)]
    .flatMap((m) => m[1].trim().split(/\s+/))
    .filter((v) => !["0", "2px", "4px", "6px", "8px", "12px", "16px", "50%", "99px", "999px"].includes(v));
  assert.deepEqual(odd, []);
});

// ── 对比度(PR #5 审查:深色下 --ink-5 #555 对卡片只有 1.9:1,占位字 / 时间 / 分组名看不清)──
function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const contrast = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test("t9 🔴 深色下承载信息的五档文字,在每一种底上都 ≥ 4.5:1(WCAG AA);禁用态另走 --disabled-*", () => {
  const bgs = ["--card", "--paper", "--paper-side", "--paper-inset", "--paper-hover"];
  const low = [];
  for (const fg of ["--ink", "--ink-2", "--ink-3", "--ink-4", "--ink-5"]) {
    for (const bg of bgs) {
      const r = contrast(DARK[fg], DARK[bg]);
      if (r < 4.5) low.push(`${fg} ${DARK[fg]} on ${bg} ${DARK[bg]} = ${r.toFixed(2)}`);
    }
  }
  assert.deepEqual(low, []);
  // 层次还在:一档比一档暗
  const L = ["--ink", "--ink-2", "--ink-3", "--ink-4", "--ink-5"].map((k) => lum(DARK[k]));
  for (let i = 1; i < L.length; i++) assert.ok(L[i] < L[i - 1], `第 ${i} 档不比上一档暗`);
  // 禁用态不借 --ink-5(借了就会跟着信息字一起变亮、看不出是禁用)
  const disabledInk5 = COMPONENTS.split("\n").filter((l) => /:disabled/.test(l) && /color: var\(--ink-5\)/.test(l));
  assert.deepEqual(disabledInk5, []);
});

test("t10 外观单选组的键盘:→↓ 下一项、←↑ 上一项(首尾循环),Home / End 到首尾,别的键不管", async () => {
  const { radioKeyTarget } = await import("../web/src/theme.ts");
  assert.equal(radioKeyTarget("ArrowRight", 0, 3), 1);
  assert.equal(radioKeyTarget("ArrowDown", 2, 3), 0);
  assert.equal(radioKeyTarget("ArrowLeft", 0, 3), 2);
  assert.equal(radioKeyTarget("ArrowUp", 1, 3), 0);
  assert.equal(radioKeyTarget("Home", 2, 3), 0);
  assert.equal(radioKeyTarget("End", 0, 3), 2);
  assert.equal(radioKeyTarget("Tab", 0, 3), null);
  assert.equal(radioKeyTarget("a", 0, 3), null);
});
