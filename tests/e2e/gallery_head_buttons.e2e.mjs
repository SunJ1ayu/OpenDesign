// 图墙题头两个按钮的形制契约 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-31 真机原话:「进入图墙后的返回项目工作区的按钮是不是应该跟在打开文件夹
// 右边才顺手?做成一样的按钮」。
//
// 主 agent 复核后**同意,并承认原设计理由站不住**:`86cf466`(0.52.0)当初刻意把
// 「← 项目工作区」做成文字链接款,理由是「册内两个返回同屏并存,同款式等于逼用户猜」。
// 但那两个返回**从来不相邻**(一个在题头、一个在 chips 下面),标签也完全不同
// (← 项目工作区 / ← 返回相册 · 参考),而文字链接混在一排按钮里读起来是"次要"——
// 对整页唯一的出口来说恰恰是错的信号,正是 07-28 反馈「图墙进得去出不来」的原病。
//
// ⚠️ 两者都改用**共享的 `.btn-secondary`**,不是让返回去抄 `.open-folder`:
// `.open-folder` 本身就是 `.btn-secondary` 的一次性复制品(仅 26px vs 28px 之差),
// 顺手收编掉,免得"做成一样的按钮"这件事变成再造第三份。
//
// 覆盖:
//   A 返回按钮在「打开文件夹」**右边**且紧挨着(同一组,间隙 ≤16px)。
//   B 两者**外观同款**:取 computed style 比(高/圆角/边框/底色/字号),不比 class 名
//     —— class 名相同不代表看起来一样,反之亦然(仓库既有做法,见 todo_rail 款式段)。
//   C 题头仍是**单行**、不换行、不越界 —— 往右边那组塞按钮最可能的真 bug 就是挤爆。
//   D 在封面墙上点「返回」= 回项目工作区。
//   E **全页只有一个返回控件,按一下回上一级**(用户 07-31 第三次拍板,见下)。
//   G 「没选中项目」那一支也有同款「返回」按钮、同样不带箭头。
//   F 按钮上**没有箭头**,文字就是「返回」(用户 07-31 追加:「不需要箭头」「太傻了
//     就写返回就可以了」)。箭头字符整类都挡掉(← → ↗ ⇦ ⧉ …),不是只挡当时那一个 ——
//     否则下次换个箭头符号照样溜进来。
//
// 跑法:node tests/e2e/gallery_head_buttons.e2e.mjs(自起 ds_web 于 8819)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8819;
const KEY = "翡翠湾-1801";
const PROJ_REL = "01-项目/20260701 王女士 翡翠湾 3#1801";

// 最小 PNG 编码器(与 gallery_order 同源:图墙必须有真图才渲染得出题头之外的内容)
function png(w, h) {
  const crcTable = [...Array(256)].map((_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const cr = Buffer.alloc(4);
    cr.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, cr]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.concat(
    [...Array(h)].map(() => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, 0x99)])),
  );
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const tmp = mkdtempSync(join(tmpdir(), "ghead-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projDir = join(ws, ...PROJ_REL.split("/"));
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 项目名**故意取长**:题头是 flex 单行,标题越长越容易把右边那组挤换行 ——
// C 段要能抓到"挤爆"就不能用短名字当夹具。
const LONG = "翡翠湾-1801 王女士 主卧全案";
writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${LONG}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-07-31
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projects: { [KEY]: PROJ_REL } }),
);

for (const album of ["主卧", "客厅", "书房"]) {
  for (const n of [1, 2]) {
    const p = join(projDir, "05-3DMAX", album, `${KEY} ${album} (${n}).png`);
    mkdirSync(dirname(p), { recursive: true });
    writeFileSync(p, png(400, 300));
  }
}

// G 段专用的**空档案库**:一个项目都没有 ⇒ GalleryPage 才会走「没选中项目」那一支
// (只要有项目,App 就自动选中一个,那一支在主夹具下永远进不去)。
const bareRoot = join(tmp, "bare");
mkdirSync(join(bareRoot, "projects"), { recursive: true });
mkdirSync(join(bareRoot, "config"), { recursive: true });
writeFileSync(join(bareRoot, "config", "workspace.json"), JSON.stringify({ projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const bareSrv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: bareRoot, DS_WEB_PORT: String(PORT + 1) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
const bareBase = `http://127.0.0.1:${PORT + 1}`;
for (const b of [base, bareBase]) {
  for (let i = 0; ; i++) {
    try { await fetch(`${b}/api/health`); break; }
    catch { if (i > 50) throw new Error(`ds_web 起不来:${b}`); await new Promise((r) => setTimeout(r, 200)); }
  }
}

// 箭头**整类**,不是只挡当时那一个符号:← → ↑ ↓ 及各种变体、全角箭头、外链方框。
// 用户 07-31:「不需要箭头」「太傻了就写返回就可以了」。
// 用码位区间写,免得靠肉眼比对字形:
//   2190–21FF 箭头 · 2794–27BF 装饰箭头 · 27F0–27FF 补充箭头A · 2900–297F 补充箭头B
//   2B00–2BFF 杂项符号与箭头 · FFE9–FFEC 全角箭头 · 29C9 外链方框(⧉)
const ARROWS =
  /[←-⇿➔-➿⟰-⟿⤀-⥿⬀-⯿￩-￬⧉]/u;

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

  const gotoGallery = async () => {
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
  };
  const back = () => page.locator('[data-ui="gallery-back-ws"]');
  // 「在不在某个相册里」的信号:页面根节点的 data-album(册内=相册 key,封面墙=空)。
  // 原来靠 `.g-back` 这个元素在不在来判断,但那个控件本轮已被合并掉了。
  const inAlbum = () => page.evaluate(
    () => !!document.querySelector(".gallery-page")?.getAttribute("data-album"));

  // 两个按钮的**看得见的事实**一次量全:位置 + computed 外观。
  // 比 computed style 而不是 class 名 —— "做成一样的按钮"是观感诉求,
  // 只有渲染出来的值能证明,class 名相同也可能被别处的规则覆盖成两个样。
  const heads = async () => page.evaluate(() => {
    const look = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return {
        left: Math.round(r.left), right: Math.round(r.right),
        top: Math.round(r.top), bottom: Math.round(r.bottom),
        h: Math.round(r.height),
        radius: s.borderTopLeftRadius,
        border: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`,
        bg: s.backgroundColor,
        fs: s.fontSize,
        color: s.color,
      };
    };
    const head = document.querySelector(".page-head");
    const kids = [...head.children].filter((e) => e.getBoundingClientRect().height > 0);
    return {
      vw: window.innerWidth,
      back: look(document.querySelector('[data-ui="gallery-back-ws"]')),
      folder: look(document.querySelector('[data-ui="gallery-open-folder"]')),
      head: look(head),
      // 单行判定:所有可见子元素的**垂直区间两两相交**(baseline 对齐下 top 未必相等,
      // 但只要没换行就一定互相重叠)。
      kidRows: kids.map((e) => {
        const r = e.getBoundingClientRect();
        return [Math.round(r.top), Math.round(r.bottom)];
      }),
      kidMaxRight: Math.max(...kids.map((e) => Math.round(e.getBoundingClientRect().right))),
    };
  });

  // ── A 返回按钮跟在「打开文件夹」右边 ─────────────────────────────────────
  await step("A 返回按钮在「打开文件夹」右边、紧挨着", async () => {
    await gotoGallery();
    const g = await heads();
    expect(g.back !== null, "题头有返回工作区按钮");
    expect(g.folder !== null, "题头有打开文件夹按钮(带 data-ui,判据能稳定抓到)");
    expect(g.back.left >= g.folder.right - 1,
      `返回在打开文件夹右边(返回左缘 ${g.back?.left} / 文件夹右缘 ${g.folder?.right})`);
    const gap = g.back.left - g.folder.right;
    expect(gap >= 0 && gap <= 16, `两者紧挨成一组(间隙 ${gap}px)`);
  });

  // ── B 外观同款 ───────────────────────────────────────────────────────────
  await step("B 两个按钮外观同款(比 computed,不比 class 名)", async () => {
    await gotoGallery();
    const g = await heads();
    for (const k of ["h", "radius", "border", "bg", "fs", "color"]) {
      expect(g.back[k] === g.folder[k],
        `${k} 一致(返回 ${JSON.stringify(g.back[k])} / 文件夹 ${JSON.stringify(g.folder[k])})`);
    }
    expect(Math.abs(g.back.top - g.folder.top) <= 1,
      `两者垂直对齐(返回 top ${g.back.top} / 文件夹 top ${g.folder.top})`);
  });

  // ── C 题头单行、不换行、不越界 ───────────────────────────────────────────
  await step("C 题头仍是单行,没被挤换行或顶出视口", async () => {
    await gotoGallery();
    const g = await heads();
    const [t0, b0] = g.kidRows[0];
    const overlapAll = g.kidRows.every(([t, b]) => t < b0 && b > t0);
    expect(overlapAll,
      `题头所有子元素同处一行(实测区间 ${JSON.stringify(g.kidRows)})`);
    // 跟**题头自己的右缘**比,不跟视口比:图墙在左侧栏右边,题头本来就比视口窄,
    // 拿视口当基准的话再挤爆也不会红(第一版就写错成这样,红检时看出来的)。
    expect(g.kidMaxRight <= g.head.right + 2,
      `题头没有元素被挤出题头右缘(最右 ${g.kidMaxRight} / 题头右缘 ${g.head.right} / 视口 ${g.vw})`);
  });

  // ── D 封面墙上点「返回」= 回工作区 ───────────────────────────────────────
  await step("D 在封面墙上点「返回」= 回项目工作区", async () => {
    await gotoGallery();
    expect(await inAlbum() === false, "前提:现在在封面墙,不在某个相册里");
    await back().click();
    await page.waitForFunction(() => location.hash === "#/workspace", { timeout: 5000 });
    expect(await page.locator(".ws-pane:not(.route-hidden)").isVisible(),
      "点了就回到项目工作区");
  });

  // ── E 全页只有一个返回,按一下回上一级 ───────────────────────────────────
  await step("E 全页只有一个返回控件,按一下回上一级", async () => {
    await gotoGallery();
    await page.locator(".g-wall .g-cell").first().click();
    await page.waitForFunction(
      () => document.querySelector(".gallery-page")?.getAttribute("data-album"),
      { timeout: 10000 });

    // ① 册内不许再有第二个返回控件(`.g-back`「← 返回相册 · X」已删)
    expect(await page.locator(".g-back").count() === 0,
      `册内没有第二个返回控件(实测 .g-back ${await page.locator(".g-back").count()} 个)`);
    expect(await back().count() === 1,
      `全页只有一个返回按钮(实测 ${await back().count()} 个)`);

    // ② 册内点它 = 回封面墙,**不离开图墙**(上一级是封面墙,不是工作区)
    await back().click();
    await page.waitForFunction(
      () => !document.querySelector(".gallery-page")?.getAttribute("data-album"),
      { timeout: 10000 });
    expect(await page.evaluate(() => location.hash) === "#/gallery",
      "册内点返回 = 回封面墙,没被踢出图墙");

    // ③ 再点一下才回工作区 —— 一个键、两级,层层往上
    await back().click();
    await page.waitForFunction(() => location.hash === "#/workspace", { timeout: 5000 });
    expect(await page.locator(".ws-pane:not(.route-hidden)").isVisible(),
      "在封面墙再点一下才回工作区(一个键、层层往上)");
  });

  // ── F 没有箭头,就写「返回」 ─────────────────────────────────────────────
  await step("F 返回按钮不带箭头,文字就是「返回」", async () => {
    await gotoGallery();
    const txt = (await back().innerText()).trim();
    expect(txt === "返回", `按钮文字是「返回」(实测 ${JSON.stringify(txt)})`);
    expect(!ARROWS.test(txt), `按钮文字不含任何箭头字符(实测 ${JSON.stringify(txt)})`);
    // 册内也是同一个按钮、同样的字(它变的是去哪,不是长相)
    await page.locator(".g-wall .g-cell").first().click();
    await page.waitForFunction(
      () => document.querySelector(".gallery-page")?.getAttribute("data-album"),
      { timeout: 10000 });
    const t2 = (await back().innerText()).trim();
    expect(t2 === "返回", `册内文字也是「返回」(实测 ${JSON.stringify(t2)})`);
  });

  // ── G 「没选中项目」那一支也别落下 ───────────────────────────────────────
  // 这一支是 0.64/0.65 两轮**漏改的地方**:主分支改了、空态没改,于是那里还留着
  // 「← 项目工作区」,而且它挂的 `.g-back-ws` 样式类当时已经被我删了 = 无样式裸按钮。
  // 判据没覆盖到的分支就是会漏 —— 补上。
  await step("G 「没选中项目」那一支也是同款「返回」、不带箭头", async () => {
    // 只要档案库里有项目,App 就会自动选中一个 ⇒ 这一支在主夹具下永远进不去。
    // 所以另起**一个空档案库的 ds_web**,专门把这一支逼出来。
    // (第一版想靠清 localStorage 把它逼出来,结果整段被 skip 掉 —— **跳过的判据
    //  等于没判**,这正是 0.64/0.65 漏改这一支的原因,不能用同样的方式再放它一马。)
    await page.goto(`${bareBase}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    const empty = page.locator(".gallery-page .muted");
    await empty.waitFor({ timeout: 15000 });
    check(await empty.count() === 1, "前提:确实进了「先在侧栏选一个项目」那一支");
    const b = back();
    expect(await b.count() === 1, "空态也有返回按钮(空页面比有内容的页面更容易困住人)");
    const txt = (await b.innerText()).trim();
    expect(txt === "返回", `空态按钮文字也是「返回」(实测 ${JSON.stringify(txt)})`);
    expect(!ARROWS.test(txt), "空态按钮也不含箭头");
    const cls = await b.getAttribute("class");
    expect(/\bbtn-secondary\b/.test(cls ?? ""),
      `空态按钮也用共享的 .btn-secondary(实测 ${JSON.stringify(cls)})`);
  });

  // ── H 全应用「打开文件夹」统一成同一个白框按钮 ───────────────────────────
  // 用户 07-31:「你说的打开文件夹我觉得也统一一下就好了,都用一样的白框然后里面字」。
  // 病历:同一个动作此前有三种写法 —— `.open-folder`(伴随列题头)/
  // `.btn-secondary sm`(伴随列空态)/ `.btn-secondary`(图墙)。
  await step("H 全应用「打开文件夹」外观一致,且一次性 class .open-folder 已不存在", async () => {
    const looks = [];
    for (const hash of ["#/workspace", "#/gallery"]) {
      await page.goto(`${base}/${hash}`, { waitUntil: "domcontentloaded" });
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1500);
      expect(await page.locator(".open-folder").count() === 0,
        `${hash}:一次性 class .open-folder 已不存在`);
      const got = await page.evaluate(() =>
        [...document.querySelectorAll("button")]
          .filter((b) => b.innerText.trim() === "打开文件夹")
          .map((b) => {
            const s = getComputedStyle(b);
            return [s.height, s.borderTopWidth, s.borderTopStyle, s.borderTopColor,
                    s.borderRadius, s.backgroundColor, s.fontSize, s.color].join(" | ");
          }));
      looks.push(...got);
    }
    check(looks.length >= 2, `前提:至少量到 2 个「打开文件夹」按钮(实测 ${looks.length} 个)`);
    const uniq = [...new Set(looks)];
    expect(uniq.length === 1,
      `所有「打开文件夹」外观完全一致(实测 ${uniq.length} 种:${JSON.stringify(uniq)})`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  bareSrv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
