// 工作区变更列:备注可写可改 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-30 真机原话:「项目工作区的待办里的备注无法修改,没有用户自己写入的通道」。
// 诊断(tasks.md A):**不是字段没人写,是一个写口两个读侧只接了一个** ——
// 后端 `note` 早在 /api/changes/edit 白名单里(ds_web.py `_EDIT_ALLOWED_KEYS`),
// 待办页有输入框(TodoPage 的 .edit-note),但 ChangesColumn 的行内编辑器只有
// new_text,备注那行是纯只读 <span class="note-tag">。而用户天天待的是工作区。
// ⇒ 本单纯前端,后端一字不动。
//
// 覆盖:
//   A 工作区行内编辑器里**有备注输入框**,且复用待办页同一套 `.edit-note`
//     (不另起第二套编辑语言 —— 与 GroupToggle/boolPrefs 同一条纪律)。
//   B 写备注 → 保存 → 行上出现「备注:…」**且磁盘 `## 变更历史` 段真落了**
//     (真写口,不是乐观 tag;TodoPage 那份是会话级 noted 映射,这里不许照抄)。
//   C 再点编辑 → 备注框**预填**既有备注(在原文上改,不是重打;待办页同口径)。
//   D **只改备注、不动正文** → 正文不变,且**不产生「改过」历史留痕**
//     (别把没改的 new_text 变成一条假留痕)。
//   E 备注 + 正文一起改 → 两者都落盘,正文那条留痕照常。
//   F 取消 → 一个字都不写。
//
// 2026-08-11 追加(track opendesign-note-clear,业主真机报「删掉原来的备注但还是之前的
// 备注」)—— 这两组连后端一起验,不再是纯前端:
//   G 工作区**清空**备注 → 磁盘那行真删掉 + 行上标签消失(邻居/留痕锚:只删备注)。
//   H 待办页写了再清 → 磁盘那行没了,且**不许留一个空的「备注:」标签**
//     (待办页的 tag 走会话级 noted 映射,存空串就会渲染成空标签)。
//
// 2026-08-11 再追加(track opendesign-note-source,业主「按第一性原理整理掉」)——
// 备注的唯一真相源必须是档案,不是浏览器会话:
//   I1 冷启动:备注经 HTTP 直接写进档案(浏览器这次会话从没写过)→ 待办页第一次
//      打开就该显示并预填。**这一条是本组最强的**:会话映射对它一无所知。
//   I2 刷新后仍在;I3 清空后刷新彻底消失(标签 + 磁盘);I4 工作区改的,待办页看得见。
//   I5 只改正文保存时,**没碰过的备注不许被回发**(否则会盖掉别人这期间刚写的);
//   I6 正文改了又改回原值 ⇒ 不许冒出假的「改过 · 看原文」(考 changed_fields 的消费者);
//   I7 是 I6 的正向锚:正文真改了,标记就必须出现(否则"把功能删掉"也能让 I6 绿);
//   I8 让前端手里的旧值与档案现值打架 —— 只有真的看服务端 changed_fields 才过得去;
//   I9 手写的空备注标记(`- Cn 备注:`)在两个页面都不许渲染成空标签(四审 LOW-3)。
//   ——(I1 改成绕开服务直接写磁盘、I5/I6 整条,都是"派活前先攻自己的题"抓出来补的)
//
// 跑法:node tests/e2e/ws_change_note.e2e.mjs(自起 ds_web 于 8816)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8816;
const TODAY = "2026-07-30";
const PROJ = "张宅-1101";

const tmp = mkdtempSync(join(tmpdir(), "wsnote-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// C1 = 已有备注(验预填);C2/C3 = 无备注(验新写入)。
// 备注行格式与写侧同处定义:`## 变更历史` 段内 `- C{n} 备注:{内容}`
// (读侧 ds_todo.HISTORY_NOTE_RE —— track opendesign-note-source 从 ds_tools 搬来的)。
writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-28 【客厅】吊顶改平顶
- [待确认] C2 2026-07-28 【主卧】衣柜加到顶
- [待确认] C3 2026-07-28 【厨房】加净水器点位

## 变更历史
- C1 备注:业主口头确认

## 沟通日志

---
最后更新: ${TODAY}
`);
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_TODAY: TODAY },
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
const md = () => readFileSync(join(dsRoot, "projects", `${PROJ}.md`), "utf-8");

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const row = (t) => page.locator(`.change-row:has-text("${t}")`);
  const noteBox = () => page.locator(".change-scroll .edit-fields .edit-note");
  const textBox = () => page.locator(".change-scroll .edit-fields .edit-text");

  // 左栏 T3 之后按阶段分堆:施工跟进不在默认收起的「已交付」堆里,直接点得到。
  const openProject = async () => {
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator(`.proj-list .proj-row:has-text("${PROJ}")`).first().click();
    await row("吊顶改平顶").waitFor({ timeout: 15000 });
  };
  // hover 才冒出图标按钮组;.edit-trigger 是编辑那颗(data-ui="change-edit")。
  const startEdit = async (t) => {
    const r = row(t);
    await r.hover();
    await r.locator(".edit-trigger").click();
    await textBox().waitFor({ timeout: 5000 });
  };

  // ── A 编辑器里有备注框 ───────────────────────────────────────────────────
  await step("A 工作区行内编辑器有备注输入框(复用待办页 .edit-note)", async () => {
    await openProject();
    await startEdit("衣柜加到顶");
    expect(await noteBox().count() === 1, "编辑态里有且只有一个 .edit-note 输入框");
    expect(await noteBox().isVisible(), "备注框可见");
  });

  // ── B 写入 → 上屏 + 落盘 ─────────────────────────────────────────────────
  await step("B 写备注保存:行上出现「备注:…」,且磁盘变更历史段真落了", async () => {
    await openProject();
    await startEdit("衣柜加到顶");
    await noteBox().fill("业主要求柜门做长虹玻璃");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("衣柜加到顶") .note-tag')
      .waitFor({ timeout: 10000 });
    const tag = await row("衣柜加到顶").locator(".note-tag").innerText();
    expect(tag.includes("业主要求柜门做长虹玻璃"), `行上备注已上屏(实测「${tag}」)`);
    expect(md().includes("- C2 备注:业主要求柜门做长虹玻璃"),
      "磁盘 `## 变更历史` 段已落 C2 备注(真写口,不是乐观 tag)");
  });

  // ── C 预填 ───────────────────────────────────────────────────────────────
  await step("C 再点编辑:备注框预填既有备注(在原文上改,不是重打)", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    expect(await noteBox().inputValue() === "业主口头确认",
      `C1 备注框预填了既有备注(实测「${await noteBox().inputValue()}」)`);
    expect(await textBox().inputValue() === "吊顶改平顶",
      "正文框同样预填(既有行为不许退化)");
  });

  // ── D 只改备注不动正文 ───────────────────────────────────────────────────
  await step("D 只改备注:正文原样,且不产生假的「改过」留痕", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    await noteBox().fill("业主书面确认");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("吊顶改平顶") .note-tag:has-text("书面")')
      .waitFor({ timeout: 10000 });
    const m = md();
    expect(m.includes("- C1 备注:业主书面确认"), "C1 备注已改写(upsert,不是追加第二行)");
    expect(!m.includes("- C1 备注:业主口头确认"), "旧备注已被替换掉");
    expect(m.includes("【客厅】吊顶改平顶"), "正文一字未动");
    expect(!/- C1 改于/.test(m), "没有假的「C1 改于 …｜原:…」留痕(正文没改就别留痕)");
  });

  // ── E 备注 + 正文一起改 ──────────────────────────────────────────────────
  await step("E 备注与正文同改:两者都落盘,正文留痕照常", async () => {
    await openProject();
    await startEdit("加净水器点位");
    await textBox().fill("加净水器和前置过滤点位");
    await noteBox().fill("水电交底前定");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("前置过滤")').waitFor({ timeout: 10000 });
    const m = md();
    expect(m.includes("加净水器和前置过滤点位"), "新正文已落盘");
    expect(m.includes("- C3 备注:水电交底前定"), "新备注已落盘");
    expect(/- C3 改于 .*原:加净水器点位/.test(m), "正文那条留痕照常写");
  });

  // ── F 取消不写入 ─────────────────────────────────────────────────────────
  await step("F 取消:一个字都不写", async () => {
    await openProject();
    const before = md();
    await startEdit("衣柜加到顶");
    await noteBox().fill("这条不该被保存");
    await page.locator(".change-scroll .edit-fields .btn-cancel").click();
    await page.waitForTimeout(500);
    expect(md() === before, "取消后档案逐字节不变");
    expect(!md().includes("这条不该被保存"), "草稿没有泄漏到磁盘");
  });
  // ── G 清空备注 = 真的删掉(track opendesign-note-clear)────────────────────
  // 业主 2026-08-11 真机原话:「我原本待办事项里备注的 我去修改删掉原来的备注但是
  // 还是之前的备注」。两层各吃掉一次:前端把"空"当成"没改"⇒ 不发请求;后端把 note=""
  // 当成"没给"⇒ 旧行留着还回 ok。**磁盘断言是这一组的锚**(页面标签会话级不算数)。
  await step("G 清空备注:磁盘那行真没了,行上标签消失(不是留个空标签)", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    expect(await noteBox().inputValue() === "业主书面确认",
      `前置:C1 现在有备注(实测「${await noteBox().inputValue()}」)`);
    await noteBox().fill("");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator(".change-scroll .edit-fields")
      .waitFor({ state: "detached", timeout: 10000 });   // 编辑器关掉 = 这一轮写完
    await page.waitForTimeout(300);
    const m = md();
    expect(!/^- C1 备注[:：]/m.test(m), "磁盘 `## 变更历史` 段里 C1 那行备注已删除");
    expect(!m.includes("业主书面确认"), "备注内容真没了");
    expect(await row("吊顶改平顶").locator(".note-tag").count() === 0,
      "行上「备注:…」标签整个消失(不是渲染成一个空的「备注:」)");
    expect(m.includes("【客厅】吊顶改平顶"), "正文一字未动");
    expect(m.includes("- C3 备注:水电交底前定"), "邻居锚:C3 的备注一个字没动");
    expect(/- C3 改于 /.test(m), "留痕锚:正文留痕行原样还在(删的只是备注)");
  });

  // ── H 待办页同样能清掉,且不留空标签 ─────────────────────────────────────
  // 待办页那个 tag 走会话级 noted 映射(数据源不带 note),**乐观回显里存空串就会
  // 渲染出一个空的「备注:」** —— 这一组专门接住那个形状。
  await step("H 待办页:写了再清 → 标签消失且磁盘那行没了", async () => {
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator('.side-row:has-text("待办事项")').first().click();
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
    const trow = page.locator('.todo-row:has-text("衣柜加到顶")').first();
    await trow.waitFor({ timeout: 10000 });
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const tnote = page.locator(".todo-row.editing .edit-note");
    await tnote.waitFor({ timeout: 5000 });
    await tnote.fill("待办页写的备注");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator('.todo-row:has-text("衣柜加到顶") .note-tag')
      .waitFor({ timeout: 10000 });
    expect(md().includes("- C2 备注:待办页写的备注"), "前置:待办页写的备注已落盘");

    const trow2 = page.locator('.todo-row:has-text("衣柜加到顶")').first();
    await trow2.hover();
    await trow2.locator(".edit-btn").click();
    const tnote2 = page.locator(".todo-row.editing .edit-note");
    await tnote2.waitFor({ timeout: 5000 });
    expect(await tnote2.inputValue() === "待办页写的备注", "编辑态预填了既有备注");
    await tnote2.fill("");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await page.waitForTimeout(300);
    expect(!md().includes("待办页写的备注"), "磁盘上那条备注真没了");
    expect(await page.locator('.todo-row:has-text("衣柜加到顶") .note-tag').count() === 0,
      "待办行上不许留一个空的「备注:」标签");
  });

  // ── I 备注的唯一真相源 = 档案(track opendesign-note-source)────────────────
  // 业主 08-11:「我觉得还是直接按第一性原理整理掉」。此前待办页的备注来自组件里
  // 一份**只活在当前网页会话**的映射(TodoPage 的 noted):刷新一下、换台电脑,
  // 备注就看不见了(工作区那侧一直是从档案读的)。这一组把它钉死在档案上。
  //
  // I1 是最强的一条:备注**不是这个浏览器会话写的**(直接打 HTTP 写进档案),
  // 页面第一次打开就该看见 —— 会话映射对它一无所知,今天必红。
  const editViaApi = (body) =>
    fetch(`${base}/api/changes/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: PROJ, ...body }),
    }).then((r) => r.json());
  const openTodoPage = async () => {
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator('.side-row:has-text("待办事项")').first().click();
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
  };
  const todoRow = (t) => page.locator(`.todo-row:has-text("${t}")`).first();
  const todoTag = (t) => page.locator(`.todo-row:has-text("${t}") .note-tag`);

  // 【攻题后加强】原来这里用 HTTP 写入,攻题(gpt-5.6-sol)点破:同一个服务进程里
  // 写完再读,**一份进程内缓存也能让它全绿** —— 它证明了"值对得上",没证明
  // "真相源是档案"。改成**绕开服务、直接改磁盘文件**。
  // 说清它到底证明了什么(第二轮攻题让我别说过头):它证明**这次待办页的读取
  // 能观察到一次绕过服务的磁盘修改**;按 mtime 失效的一致性缓存仍能通过 ——
  // 但那种缓存不产生业主可见的错误,不是这条要防的东西。
  const writeNoteOnDisk = (cnum, note) => {
    const lines = md().split("\n").filter((l) => !l.startsWith(`- C${cnum} 备注`));
    const i = lines.indexOf("## 变更历史");
    lines.splice(i + 1, 0, `- C${cnum} 备注:${note}`);
    writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), lines.join("\n"));
  };

  await step("I1 冷启动:档案里已有的备注,待办页第一次打开就显示并预填", async () => {
    writeNoteOnDisk(3, "冷启动也要看得见");     // 绕开服务,直接落盘
    expect(md().includes("- C3 备注:冷启动也要看得见"), "前置:磁盘上确实有这条");

    await openTodoPage();
    await todoRow("前置过滤").waitFor({ timeout: 10000 });
    expect(await todoTag("前置过滤").count() === 1,
      "待办行上有「备注:」标签(浏览器这次会话从没写过它 ⇒ 只能是从档案读的)");
    expect((await todoTag("前置过滤").innerText()).includes("冷启动也要看得见"),
      "标签里是档案里那句话");

    const trow = todoRow("前置过滤");
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const box = page.locator(".todo-row.editing .edit-note");
    await box.waitFor({ timeout: 5000 });
    expect(await box.inputValue() === "冷启动也要看得见", "编辑框预填的也是档案里那句");
    await page.locator(".todo-row.editing .btn-cancel").click().catch(() => {});
  });

  await step("I2 刷新:待办页写的备注,F5 之后还在", async () => {
    await openTodoPage();
    const trow = todoRow("衣柜加到顶");
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const box = page.locator(".todo-row.editing .edit-note");
    await box.waitFor({ timeout: 5000 });
    await box.fill("刷新之后还得在");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    expect(md().includes("- C2 备注:刷新之后还得在"), "前置:落盘了");

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
    await todoRow("衣柜加到顶").waitFor({ timeout: 10000 });
    expect(await todoTag("衣柜加到顶").count() === 1, "刷新后标签还在(今天必红)");
    expect((await todoTag("衣柜加到顶").innerText()).includes("刷新之后还得在"),
      "刷新后显示的还是那句话");
  });

  await step("I3 清空之后刷新:标签没了,磁盘那行也没了", async () => {
    const trow = todoRow("衣柜加到顶");
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const box = page.locator(".todo-row.editing .edit-note");
    await box.waitFor({ timeout: 5000 });
    expect(await box.inputValue() === "刷新之后还得在", "编辑框预填的是档案里的现值");
    await box.fill("");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
    await todoRow("衣柜加到顶").waitFor({ timeout: 10000 });
    expect(await todoTag("衣柜加到顶").count() === 0, "刷新后标签不再出现");
    expect(!md().includes("刷新之后还得在"), "磁盘那行真没了");
  });

  await step("I4 跨面一致:工作区改的备注,待办页看到的是新值", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    await noteBox().fill("工作区改的,待办页也该看见");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator(".change-scroll .edit-fields")
      .waitFor({ state: "detached", timeout: 10000 });
    expect(md().includes("- C1 备注:工作区改的,待办页也该看见"), "前置:工作区写进去了");

    await openTodoPage();
    await todoRow("吊顶改平顶").waitFor({ timeout: 10000 });
    expect((await todoTag("吊顶改平顶").innerText()).includes("工作区改的,待办页也该看见"),
      "两个页面同一个真相源");
  });

  // 【攻题后新增】I5/I6 —— 攻题给出的那份"全绿但业主仍会丢数据/看到假标记"的实现,
  // 就是靠这两条接住的。它们考的不是请求装配函数,是**页面真的怎么用它**。
  //
  // ⚠️ 老实说清它俩的性质:**今天(旧实现)它们的主断言基本是绿的** ——
  // 旧 buildEditRequest 会把"与原值相同"的字段整个丢掉,所以既不会回发没碰过的备注,
  // 也不会给原样保存打上"改过"。它们**不是红检证据**,是**防坑锚**:
  // 本单把那道"值比较"拆掉之后,坑才会出现,而这两条守在坑口。
  // (I5 里唯一今天就红的是那句前置——待办页现在根本预填不出档案里的备注。)

  // I5:业主没碰过的字段,不许被回发。
  // 场景(攻题原话的复现):他打开编辑器 → 这期间助手/另一台电脑改了备注 →
  // 他只改正文就保存 ⇒ 如果编辑器把"打开时预填的旧备注"一起发回去,
  // 后端会诚实地把别人刚写的新备注**盖回旧值**。业主眼里:我只改了正文,
  // 备注怎么变回去了。("陈旧编辑保护"是另一单,但这一单不许把窗口开大。)
  await step("I5 只改正文保存:别人这期间改的备注不许被盖回去", async () => {
    writeNoteOnDisk(2, "现场待定");
    await openTodoPage();
    const trow = todoRow("衣柜加到顶");
    await trow.waitFor({ timeout: 10000 });
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const box = page.locator(".todo-row.editing .edit-note");
    await box.waitFor({ timeout: 5000 });
    expect(await box.inputValue() === "现场待定", "前置:编辑框预填的是档案里的现值");

    // 编辑器开着的时候,别人改了备注(走真写口,和助手/另一台电脑同一条路)
    const r = await editViaApi({ cnum: 2, note: "业主确认取消" });
    expect(r.ok === true, `前置:别人经写口改了备注(${JSON.stringify(r)})`);

    // 他只碰正文
    const textbox = page.locator(".todo-row.editing .edit-text");
    await textbox.fill("衣柜加到顶并做见光板");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await page.waitForTimeout(300);

    const m = md();
    expect(m.includes("- C2 备注:业主确认取消"), "别人写的备注还在(没被旧值盖回去)");
    expect(!m.includes("现场待定"), "打开编辑器时的旧备注没有被回发");
    expect(m.includes("衣柜加到顶并做见光板"), "他改的正文照常落盘");
  });

  // I6:改了又改回原值 ⇒ 不许出现「改过 · 看原文」。
  // 这一条考的是 changed_fields 的**消费者**:后端算得再对,前端要是还看
  // "请求里带没带 new_text",原样保存也会被标成改过。
  await step("I6 正文改了又改回原值:不许冒出「改过 · 看原文」", async () => {
    await openTodoPage();
    const trow = todoRow("前置过滤");
    await trow.waitFor({ timeout: 10000 });
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const textbox = page.locator(".todo-row.editing .edit-text");
    await textbox.waitFor({ timeout: 5000 });
    const original = await textbox.inputValue();
    await textbox.fill("先改成别的");
    await textbox.fill(original);                     // 又改回来
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await page.waitForTimeout(300);
    expect(await page.locator('.todo-row:has-text("前置过滤") .edited-tag').count() === 0,
      "没有假的「改过 · 看原文」标记(以服务端 changed_fields 为准)");
    expect(!/- C3 改于 .*原:加净水器和前置过滤点位/.test(md()),
      "磁盘上也不许留假留痕");
  });

  // I7:I6 的**正向锚**。第二轮攻题点破 I6 只是负向的 ——
  // 把「改过 · 看原文」这个功能整个删掉,I6 照样绿。所以再钉一条:
  // 正文**真的改了**,标记就必须出现。两条一起才等于"以 changed_fields 为准"。
  await step("I7 正文真改了:「改过 · 看原文」必须出现", async () => {
    await openTodoPage();
    const trow = todoRow("前置过滤");
    await trow.waitFor({ timeout: 10000 });
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const textbox = page.locator(".todo-row.editing .edit-text");
    await textbox.waitFor({ timeout: 5000 });
    await textbox.fill("加净水器和前置过滤点位(位置待定)");
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await page.waitForTimeout(300);
    expect(await page.locator('.todo-row:has-text("位置待定") .edited-tag').count() === 1,
      "正文真改了 ⇒ 行上出现「改过 · 看原文」");
    expect(md().includes("- [待确认] C3 2026-07-28 【厨房】加净水器和前置过滤点位(位置待定)"),
      "磁盘上正文真的变成了新值");
    expect(/- C3 改于 .*原:加净水器和前置过滤点位/.test(md()),
      "磁盘上也留了真留痕");
  });

  // I8:把"到底谁说了算"钉死。第三轮攻题指出 I6+I7 还不够 ——
  // 前端只要拿"提交值 vs 打开编辑器时看到的旧值"自己比一遍,也能让 I6/I7 都绿,
  // **根本不看服务端的 changed_fields**。要拆穿它,得让两边的判断打架:
  //   编辑器开着 → 别人把正文改成 X → 业主也正好把正文改成 X 并保存。
  // 前端手里的旧值是 X 之前那个,自己比 ⇒ "改了" ⇒ 会打上「改过」;
  // 而档案里本来就已经是 X ⇒ 服务端 changed_fields=[] ⇒ 标记不该出现,也不该留痕。
  await step("I8 前端旧值与档案现值打架:以档案为准(不许出现「改过」)", async () => {
    await openTodoPage();
    const trow = todoRow("位置待定");
    await trow.waitFor({ timeout: 10000 });
    await trow.hover();
    await trow.locator(".edit-btn").click();
    const textbox = page.locator(".todo-row.editing .edit-text");
    await textbox.waitFor({ timeout: 5000 });

    // 别人先把正文改成了 X(走真写口)
    const X = "加净水器和前置过滤点位(已定在阳台)";
    const r = await editViaApi({ cnum: 3, new_text: X });
    expect(r.ok === true, `前置:别人把正文改成了 X(${JSON.stringify(r)})`);

    // 【第四轮攻题抓到我这条自己的两个 bug,已修】
    // ① 原来断言"不许有 `原:…(位置待定)` 这条留痕"——**必然失败**:别人改成 X
    //    那一次本来就会合法地留下它。正确的锚是**业主这次保存前后档案逐字节不变**。
    // ② 原来保存完只等 300ms 就对还没渲染出来的行做 count()===0 —— 行没出来也会绿。
    //    改成先等行出现再看标记。
    const snap = md();          // 别人改完之后的档案快照 = 业主这次保存的期望值

    // 业主也正好改成同一个 X —— 他手里的旧值是过期的
    await textbox.fill(X);
    await page.locator(".todo-row.editing .btn-save").click();
    await page.locator(".todo-row.editing").waitFor({ state: "detached", timeout: 10000 });
    await todoRow("已定在阳台").waitFor({ timeout: 10000 });   // 先等行真的刷出来

    expect(md() === snap, "业主这次保存前后,档案逐字节不变(他改成的正是现值)");
    expect(await page.locator('.todo-row:has-text("已定在阳台") .edited-tag').count() === 0,
      "不许出现「改过 · 看原文」—— 前端拿自己手里的旧值比,就会在这条上露馅");
  });


  // I9(四审 subdeepseek LOW-3):**手写的空备注标记**。老档案里可能有一行
  // `- C2 备注:`(冒号后什么都没有)—— 写侧永远不产生它(清空是删行,不是置空),
  // 只可能来自人手改档案。读侧会解析出 note:"",于是"有这个键"⇒ 页面渲染出一个
  // 空的「备注:」标签。上一单刚在待办页消灭过空标签(H 组),这一单又给待办页
  // **新开了一个能长出它的面**(备注现在来自服务端载荷)⇒ 两个页面都不许渲染它。
  await step("I9 手写的空备注标记:两个页面都不许渲染出一个空的「备注:」", async () => {
    const lines = md().split("\n").filter((l) => !l.startsWith("- C2 备注"));
    const hi = lines.indexOf("## 变更历史");
    lines.splice(hi + 1, 0, "- C2 备注:");        // 冒号后为空,手写档案才有的形状
    writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), lines.join("\n"));

    await openTodoPage();
    await todoRow("衣柜加到顶").waitFor({ timeout: 10000 });
    expect(await todoTag("衣柜加到顶").count() === 0,
      "待办页:空备注标记不许渲染成一个空的「备注:」标签");

    await openProject();
    expect(await row("衣柜加到顶").locator(".note-tag").count() === 0,
      "工作区同样不许(这条毛病它一直有,顺手一起堵)");
  });

} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
