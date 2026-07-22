// track opendesign-todo-duedate e2e:真 ds_web(参照 frontend_p2_polish.e2e.mjs 起服务写法),
// 纯 API 层(无浏览器——契约是 POST /api/changes/due 的行为,不是某个前端交互细节)。
// 覆盖:设截止日 → /api/changes 读回带 due → 清除 → 读回 null → edit_change 改正文后 due 仍在。
//
// 跑法:node tests/e2e/duedate.e2e.mjs(自起 ds_web 于 8795)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8795;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "duedate-e2e-"));
const dsRoot = join(tmp, "ds");
const proj = "翡翠湾-1801";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${proj}.md`), `# ${proj}

- 业主: [[张三]]
- 阶段: 方案深化

## 变更记录
- [待确认] C1 2026-07-15 【玄关】玄关柜改高
- [进行中] C2 2026-07-10 电视墙放样

## 沟通日志

---
最后更新: 2026-06-20
`);

// ── 起 ds_web ───────────────────────────────────────────────────────────────
const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

async function postDue(body) {
  const r = await fetch(`${base}/api/changes/due`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let json = null;
  try { json = await r.json(); } catch { /* 非 JSON 响应忽略 */ }
  return { status: r.status, json };
}

async function fetchChanges() {
  const r = await fetch(`${base}/api/projects/${encodeURIComponent(proj)}/changes`);
  const d = await r.json();
  return d.changes;
}

function findCnum(changes, cnum) {
  return changes.find((c) => c.cnum === cnum);
}

let failures = 0;
try {
  // 1. 设截止日
  const r1 = await postDue({ project: proj, cnum: 1, due: "2026-07-31" });
  check(r1.status === 200 && r1.json?.ok === true, "POST /api/changes/due:设截止日 200 + ok");

  // 2. /api/changes 读回带 due
  let changes = await fetchChanges();
  check(findCnum(changes, 1)?.due === "2026-07-31", "GET /api/changes:C1 带回 due=2026-07-31");
  check(findCnum(changes, 1)?.text === "玄关柜改高", "GET /api/changes:C1 正文不含 ⏳,字节干净");
  check(findCnum(changes, 2)?.due === null, "GET /api/changes:未设截止日的 C2 due=null");

  // 3. 清除(due: null)
  const r2 = await postDue({ project: proj, cnum: 1, due: null });
  check(r2.status === 200 && r2.json?.ok === true, "POST /api/changes/due:清除 200 + ok");
  changes = await fetchChanges();
  check(findCnum(changes, 1)?.due === null, "GET /api/changes:清除后 C1 due=null");

  // 4. 非法日期 → 400 invalid_due
  const r3 = await postDue({ project: proj, cnum: 2, due: "下周五" });
  check(r3.status === 400 && r3.json?.error === "invalid_due", "POST /api/changes/due:非法日期 400 invalid_due");

  // 5. 不存在的变更 → 404 change_not_found
  const r4 = await postDue({ project: proj, cnum: 99, due: "2026-08-01" });
  check(r4.status === 404 && r4.json?.error === "change_not_found", "POST /api/changes/due:不存在的 cnum 404 change_not_found");

  // 6. 多余键 → 400(键白名单)
  const r5 = await postDue({ project: proj, cnum: 2, due: "2026-08-01", extra: "x" });
  check(r5.status === 400, "POST /api/changes/due:多余键拒(键白名单)");

  // 7. edit_change 改正文后 due 仍在
  const r6 = await postDue({ project: proj, cnum: 2, due: "2026-08-01" });
  check(r6.status === 200, "先给 C2 设截止日(为改正文回归铺垫)");
  const rEdit = await fetch(`${base}/api/changes/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project: proj, cnum: 2, new_text: "电视墙放样改到 3.2 米" }),
  });
  check(rEdit.status === 200, "POST /api/changes/edit:改正文 200");
  changes = await fetchChanges();
  const c2 = findCnum(changes, 2);
  check(c2?.text === "电视墙放样改到 3.2 米", "改正文后:text 更新");
  check(c2?.due === "2026-08-01", "改正文后:due 未丢(仍是 2026-08-01)");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "DUEDATE E2E: ALL PASS" : `DUEDATE E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
