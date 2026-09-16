// 判据:e2e 判据进程不许有外网出口 + 浏览器临时目录归测试自己收(track opendesign-e2e-no-egress-browser-tmp)。
// 编号权威表在 tracks/archive/opendesign-e2e-no-egress-browser-tmp/design.md(ne0~ne10、bt1~bt3)
// 与 tracks/opendesign-e2e-guard-followup/design.md(bt4 重写、bt5、ne11、ne12)。
// 跑法:node --test tests/test_e2e_harness_guard.mjs
//
// 真 unshare、真 chromium。场景脚本都写在临时目录里、按绝对路径导入真 helpers.mjs。
// 🔴 本文件自己**绝不能** import helpers.mjs:它导入即生效,会把本测试进程也搬进无网命名空间,
//    ne0 那条前提就再也问不出来了。要读 helpers 的导出,一律起一个子进程去读。
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, existsSync, rmSync, mkdirSync, chmodSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const E2E_DIR = path.join(REPO, "tests", "e2e");
const HELPERS_URL = pathToFileURL(path.join(E2E_DIR, "helpers.mjs")).href;
const PY = process.env.PY || "/root/.venvs/design-studio/bin/python";
const EGRESS_PROBE = ["-c", "exec 3<>/dev/tcp/1.1.1.1/443"];

function tmp(prefix) {
  return mkdtempSync(path.join(os.tmpdir(), prefix));
}

/** 写一个"e2e 形状"的场景脚本:先导入真 helpers,再跑 body。 */
function scenario(dir, name, body) {
  const file = path.join(dir, name);
  writeFileSync(file, `import * as H from ${JSON.stringify(HELPERS_URL)};\n${body}\n`);
  return file;
}

/** 场景里通用的"记事实"代码:执行次数、自己的 net ns、1 号进程的 net ns、连不连得出去。 */
const FACTS_BODY = `
import { appendFileSync as __a, writeFileSync as __w, readlinkSync as __r } from "node:fs";
import { spawnSync as __s } from "node:child_process";
__a(process.env.GUARD_MARKER, "ran\\n");
__w(process.env.GUARD_FACTS, JSON.stringify({
  self: __r("/proc/self/ns/net"),
  host: __r("/proc/1/ns/net"),
  egress: __s("bash", ${JSON.stringify(EGRESS_PROBE)}, { timeout: 3000, stdio: "ignore" }).status === 0,
}));
`;

function run(cmd, args, { env = {}, input } = {}) {
  return spawnSync(cmd, args, {
    env: { ...process.env, ...env },
    encoding: "utf8",
    timeout: 120000,
    input,
  });
}

function markerCount(marker) {
  return existsSync(marker) ? readFileSync(marker, "utf8").split("\n").filter(Boolean).length : 0;
}

function fakeUnshareDir() {
  const d = tmp("ds-guardtest-fakebin-");
  const f = path.join(d, "unshare");
  writeFileSync(f, "#!/bin/sh\nexit 1\n");
  chmodSync(f, 0o755);
  return d;
}

test("ne0 前提:本测试进程(主网络命名空间)连得上 1.1.1.1:443 —— 连不上就问不出「守卫切断了出口」", () => {
  const r = spawnSync("bash", EGRESS_PROBE, { timeout: 5000, stdio: "ignore" });
  assert.equal(r.status, 0,
    "主命名空间里本来就连不出去 ⇒ ne1/ne7 的「连不上」分不清是守卫挡的还是本来就没网。这不是通过,是问不出来");
});

test("ne1 导入 helpers 的普通 e2e:在独立网络命名空间里、连不上外网、场景代码只跑一次", () => {
  const d = tmp("ds-guardtest-ne1-");
  try {
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], { env: { GUARD_MARKER: marker, GUARD_FACTS: facts } });
    assert.equal(r.status, 0, `场景没跑成:rc=${r.status}\n${r.stderr}`);
    const f = JSON.parse(readFileSync(facts, "utf8"));
    assert.notEqual(f.self, f.host, "e2e 还在主网络命名空间里跑 —— 判据有外网出口");
    assert.equal(f.egress, false, "在独立命名空间里却仍然连得出去");
    assert.equal(markerCount(marker), 1, "场景代码跑了不止一次(守卫在场景之后才 re-exec?)");
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("ne2 unshare 用不了 ⇒ 拒跑 rc=78、说清是无出口守卫、场景一行没跑", () => {
  const d = tmp("ds-guardtest-ne2-"), fb = fakeUnshareDir();
  try {
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], {
      env: { GUARD_MARKER: marker, GUARD_FACTS: facts, PATH: `${fb}:${process.env.PATH}` },
    });
    assert.equal(r.status, 78, `隔离做不到却没有拒跑:rc=${r.status}\n${r.stderr}`);
    assert.match(r.stderr, /无出口守卫/);
    assert.equal(markerCount(marker), 0, "拒跑之前场景代码已经跑了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

test("ne3 透传:场景的退出码与命令行参数原样", () => {
  const d = tmp("ds-guardtest-ne3-");
  try {
    const file = scenario(d, "probe.e2e.mjs",
      `process.stdout.write(JSON.stringify(process.argv.slice(2))); process.exit(7);`);
    const args = ["带 空格", "--x=1"];
    const r = run(process.execPath, [file, ...args]);
    assert.equal(r.status, 7, `退出码没透传:rc=${r.status}\n${r.stderr}`);
    assert.deepEqual(JSON.parse(r.stdout), args);
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("ne4 豁免:要活网关的两条(new_chat / project-thread)留在主网络命名空间", () => {
  for (const name of ["new_chat.e2e.mjs", "project-thread.e2e.mjs"]) {
    const d = tmp("ds-guardtest-ne4-");
    try {
      const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
      const file = scenario(d, name, FACTS_BODY);
      const r = run(process.execPath, [file], { env: { GUARD_MARKER: marker, GUARD_FACTS: facts } });
      assert.equal(r.status, 0, `${name} 没跑成:rc=${r.status}\n${r.stderr}`);
      const f = JSON.parse(readFileSync(facts, "utf8"));
      assert.equal(f.self, f.host, `${name} 被搬进了无网命名空间 —— 它要连主命名空间里的活网关与 8768`);
      assert.equal(markerCount(marker), 1);
    } finally { rmSync(d, { recursive: true, force: true }); }
  }
});

test("ne5 豁免名单单一来源:helpers 的 NEEDS_LIVE_GATEWAY == run-all.sh 的 NEEDS_GATEWAY", () => {
  const d = tmp("ds-guardtest-ne5-");
  try {
    // 用豁免名字起子进程去读导出(本进程不许导入 helpers,见文件头)
    const file = scenario(d, "new_chat.e2e.mjs",
      `process.stdout.write(JSON.stringify(H.NEEDS_LIVE_GATEWAY ?? null));`);
    const r = run(process.execPath, [file]);
    assert.equal(r.status, 0, r.stderr);
    const fromHelpers = JSON.parse(r.stdout);
    assert.ok(Array.isArray(fromHelpers), "helpers.mjs 没有导出 NEEDS_LIVE_GATEWAY 数组");
    const sh = run("bash", ["-c",
      `eval "$(grep -E '^NEEDS_GATEWAY=' "$1")"; printf '%s' "$NEEDS_GATEWAY"`, "_", path.join(E2E_DIR, "run-all.sh")]);
    const fromRunAll = sh.stdout.split(/\s+/).filter(Boolean);
    assert.ok(fromRunAll.length > 0, "run-all.sh 里没读出 NEEDS_GATEWAY");
    assert.deepEqual([...fromHelpers].sort(), [...fromRunAll].sort());
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("ne6 环境变量不是身份牌:主命名空间里预设 DS_E2E_NOEGRESS_TRIED ⇒ 拒跑、场景没跑", () => {
  const d = tmp("ds-guardtest-ne6-");
  try {
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], {
      env: { GUARD_MARKER: marker, GUARD_FACTS: facts, DS_E2E_NOEGRESS_TRIED: "1" },
    });
    assert.equal(r.status, 78, `一个环境变量就让守卫放行了:rc=${r.status}\n${r.stderr}`);
    assert.equal(markerCount(marker), 0);
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("ne7 python 版:导入 tests/e2e/_no_egress.py 的脚本在独立命名空间、连不上外网;unshare 用不了 ⇒ rc=78 且脚本体没跑", () => {
  const d = tmp("ds-guardtest-ne7-"), fb = fakeUnshareDir();
  try {
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = path.join(d, "probe.e2e.py");
    writeFileSync(file, `import json, os, subprocess, sys
sys.path.insert(0, ${JSON.stringify(E2E_DIR)})
import _no_egress  # noqa: F401
open(os.environ["GUARD_MARKER"], "a").write("ran\\n")
egress = subprocess.call(["bash", "-c", "exec 3<>/dev/tcp/1.1.1.1/443"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3) == 0
json.dump({"self": os.readlink("/proc/self/ns/net"), "host": os.readlink("/proc/1/ns/net"),
           "egress": egress}, open(os.environ["GUARD_FACTS"], "w"))
`);
    const env = { GUARD_MARKER: marker, GUARD_FACTS: facts };
    const r = run(PY, [file], { env });
    assert.equal(r.status, 0, `python 场景没跑成:rc=${r.status}\n${r.stderr}`);
    const f = JSON.parse(readFileSync(facts, "utf8"));
    assert.notEqual(f.self, f.host, "python e2e 还在主网络命名空间里");
    assert.equal(f.egress, false);
    assert.equal(markerCount(marker), 1);

    rmSync(marker, { force: true });
    const r2 = run(PY, [file], { env: { ...env, PATH: `${fb}:${process.env.PATH}` } });
    assert.equal(r2.status, 78, `python 版隔离做不到却没拒跑:rc=${r2.status}\n${r2.stderr}`);
    assert.equal(markerCount(marker), 0);
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

test("ne8 结构:每个 .e2e.mjs 都导入 ./helpers.mjs;每个 .e2e.py 都 import _no_egress 且在 import ds_ 之前", () => {
  const files = readdirSync(E2E_DIR);
  const mjs = files.filter((f) => f.endsWith(".e2e.mjs"));
  const py = files.filter((f) => f.endsWith(".e2e.py"));
  assert.ok(mjs.length >= 30 && py.length >= 3, `e2e 文件数不对劲:mjs=${mjs.length} py=${py.length}`);
  for (const f of mjs) {
    const src = readFileSync(path.join(E2E_DIR, f), "utf8");
    assert.match(src, /^\s*import\s[^;]*?from\s+["']\.\/helpers\.mjs["']/m, `${f} 没导入 ./helpers.mjs ⇒ 无出口守卫管不到它`);
  }
  for (const f of py) {
    const lines = readFileSync(path.join(E2E_DIR, f), "utf8").split("\n");
    const guard = lines.findIndex((l) => /^import _no_egress\b/.test(l));
    const firstDs = lines.findIndex((l) => /^\s*(import|from)\s+ds_/.test(l));
    assert.ok(guard >= 0, `${f} 没有顶格的 import _no_egress`);
    if (firstDs >= 0) assert.ok(guard < firstDs, `${f} 的 import _no_egress 在 import ds_ 之后`);
  }
});

// ── bt:浏览器临时目录 ──────────────────────────────────────────────────────

function leftovers(dir) {
  return readdirSync(dir).filter((n) => !n.startsWith("node-compile-"));
}

// 两种没走正常关闭的真实形状(09-15 实测各 3 次都留 org.chromium.Chromium.*):
//   exit-open —— 浏览器开着就 process.exit(场景崩了、或忘了 close);sigkill —— 浏览器主进程被硬杀。
// ⚠️ Playwright 的 Browser 没有 process() —— 第一版判据这么写,红在 TypeError 上而不是泄漏上(红得不对)。
//    主进程 pid 从本进程的子进程里找。
const BT1_SCENARIOS = {
  "exit-open": `
const browser = await H.launchBrowser();
const page = await browser.newPage();
await page.setContent("<p>x</p>");
process.exit(0);`,
  "sigkill": `
import { execSync } from "node:child_process";
const browser = await H.launchBrowser();
const page = await browser.newPage();
await page.setContent("<p>x</p>");
const pids = execSync("ps -o pid=,args= --ppid " + process.pid).toString().trim().split("\\n")
  .filter((l) => /chrome/.test(l)).map((l) => Number(l.trim().split(/\\s+/)[0]));
if (pids.length === 0) { process.stderr.write("找不到浏览器主进程\\n"); process.exit(5); }
for (const p of pids) process.kill(p, "SIGKILL");
await new Promise((r) => setTimeout(r, 800));
process.exit(0);`,
};

test("bt1 浏览器没走正常关闭(开着就退出 / 主进程被硬杀):外层 TMPDIR 剩 0 个;stderr 点名;E2E_BROWSER_NOTES 记一行", () => {
  for (const [mode, body] of Object.entries(BT1_SCENARIOS)) {
    const d = tmp("ds-guardtest-bt1-"), outer = tmp("ds-guardtest-bt1-tmp-");
    try {
      const notes = path.join(d, "notes.txt");
      const name = `probe-${mode}.e2e.mjs`;
      const file = scenario(d, name, body);
      const r = run(process.execPath, [file], { env: { TMPDIR: outer, TMP: outer, TEMP: outer, E2E_BROWSER_NOTES: notes } });
      assert.equal(r.status, 0, `[${mode}] 场景没跑成:rc=${r.status}\n${r.stderr}`);
      assert.deepEqual(leftovers(outer), [], `[${mode}] 浏览器没正常关闭,它的临时目录留在了外层 TMPDIR`);
      assert.match(r.stderr, /浏览器没走正常关闭/, `[${mode}] 收掉了却没点名 —— 泄漏闸从此看不见这件事`);
      assert.ok(existsSync(notes), `[${mode}] 设了 E2E_BROWSER_NOTES 却没记`);
      assert.match(readFileSync(notes, "utf8"), new RegExp("^" + name.replace(/[.]/g, "\\.") + ":", "m"));
    } finally { rmSync(d, { recursive: true, force: true }); rmSync(outer, { recursive: true, force: true }); }
  }
});

// ── 第 1 轮评审(subdeepseek,2026-09-16)三条成立发现补的判据 ──────────────

test("ne9 回环起不来不许静默:假 ip 让 lo 起不来 ⇒ 打守卫横幅并拒跑(别红成「产品坏了」的样子)", () => {
  // 🔴 由来:守卫自举时 `ip link set lo up 2>/dev/null || true` 把失败吞了。
  // 吞掉的后果不是边角:3 个 .e2e.py 和绝大多数 .e2e.mjs 都要自起 ds_web 走 127.0.0.1,
  // lo 没起来它们全部 ENETUNREACH ⇒ 红在"连不上自己的服务"上,而那和"产品坏了"长得一模一样。
  // design.md 风险 4 写的是"响亮地红,不静默" —— 这条判据钉的就是那句话。
  const d = tmp("ds-guardtest-ne9-"), fb = tmp("ds-guardtest-ne9-fakebin-");
  try {
    const fake = path.join(fb, "ip");
    writeFileSync(fake, "#!/bin/sh\nexit 1\n");
    chmodSync(fake, 0o755);
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], {
      env: { GUARD_MARKER: marker, GUARD_FACTS: facts, PATH: `${fb}:${process.env.PATH}` },
    });
    assert.equal(r.status, 78, `lo 起不来却照跑:rc=${r.status}\n${r.stderr}`);
    assert.match(r.stderr, /无出口守卫/, "红了,但没说是守卫的事 —— 下一个人会去查产品");
    assert.match(r.stderr, /回环/, "没点明是回环(lo)起不来");
    assert.equal(markerCount(marker), 0, "回环坏了还把场景跑了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

test("ne10 探针过了但自举失败 ⇒ 仍要打横幅,不许裸着退出", () => {
  // 🔴 由来:探针用 `unshare -n -- true`,真自举用 `unshare -n -- bash -c …`。
  // 只有探针那一支有横幅;探针过、真自举挂时打印 0 行解释、rc 是个裸数字。
  const d = tmp("ds-guardtest-ne10-"), fb = tmp("ds-guardtest-ne10-fakebin-");
  try {
    const fake = path.join(fb, "unshare");
    // 探针(`-- true`)放行,真自举(`-- bash`)失败 —— 精确模拟"探得过、跑不动"。
    writeFileSync(fake, '#!/bin/sh\nfor a in "$@"; do [ "$a" = "true" ] && exec /usr/bin/env true; done\nexit 3\n');
    chmodSync(fake, 0o755);
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], {
      env: { GUARD_MARKER: marker, GUARD_FACTS: facts, PATH: `${fb}:${process.env.PATH}` },
    });
    assert.match(r.stderr, /无出口守卫/, `自举失败却一句解释都没有:rc=${r.status}\n${r.stderr}`);
    assert.equal(markerCount(marker), 0, "自举失败还把场景跑了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

// ── 本单 opendesign-e2e-guard-followup(2026-09-16)────────────────────────
// 上一单第 2 轮 DeepSeek 的 BLOCK 复现成立:旧 bt4 只查「文本里有那句话、排在 note_last 之前」,
// 把 tests/run-all.sh 两行计数代码删掉它照样绿(那句话在注释里也有);它放过的计数也错(1 次报 2 次)。
// ⇒ 旧 bt4 删掉。下面两条都是**抽出真脚本的一段来跑**,锚点抽不到就响亮地红。

const sh = (s) => "'" + String(s).replace(/'/g, "'\\''") + "'";

function envWithout(key) {
  const { [key]: _drop, ...rest } = process.env;
  return rest;
}

/** 从真脚本里抽 start(含)到 end(不含)那一段。抽不到就红 —— 标题改名要连判据一起改,不许静默变空。 */
function section(file, start, end) {
  const text = readFileSync(file, "utf8");
  const i = text.indexOf(start);
  const j = i >= 0 ? text.indexOf(end, i + start.length) : -1;
  assert.ok(i >= 0 && j > i,
    `抽不到 ${path.relative(REPO, file)} 里「${start}」到「${end}」那一段 —— 锚点改名了就连判据一起改`);
  return text.slice(i, j);
}

/** 用**真 helpers** 造点名(不是判据里的字面量):每个名字跑一次「开着浏览器就退出」,helpers 记一行。 */
function realBrowserNotes(dir, names) {
  const notes = path.join(dir, "real-notes.txt");
  const outer = tmp("ds-guardtest-notes-tmp-");
  try {
    for (const name of names) {
      const file = scenario(dir, name, BT1_SCENARIOS["exit-open"]);
      const r = run(process.execPath, [file], {
        env: { TMPDIR: outer, TMP: outer, TEMP: outer, E2E_BROWSER_NOTES: notes },
      });
      assert.equal(r.status, 0, `造点名的场景没跑成(${name}):rc=${r.status}\n${r.stderr}`);
    }
  } finally { rmSync(outer, { recursive: true, force: true }); }
  const lines = existsSync(notes) ? readFileSync(notes, "utf8").split("\n").filter(Boolean) : [];
  assert.equal(lines.length, names.length, `真 helpers 没有按次记点名(前提不成立,问不下去):\n${lines.join("\n")}`);
  return notes;
}

/** 桩掉 run_seg / note_last,跑外层 ⑥ e2e 段;假内层 = fakeInner(一段 bash)。返回喂给 note_last 的那句。 */
function outerE2eNote(dir, fakeInner) {
  const seg = section(path.join(REPO, "tests", "run-all.sh"), "# ── ⑥ e2e 总跑", "# ── 汇总");
  const inner = path.join(dir, "fake-inner.sh");
  writeFileSync(inner, `#!/usr/bin/env bash\n${fakeInner}\n`);
  chmodSync(inner, 0o755);
  const logDir = path.join(dir, "outer-log");
  mkdirSync(logDir);
  const noteOut = path.join(dir, "note.out");
  const harness = `set -uo pipefail
with_gateway=0
log_dir=${sh(logDir)}
run_seg() { shift 2; ${sh(inner)} >"$log_dir/e2e.log" 2>&1; LAST_RC=$?; LAST_LOG="$log_dir/e2e.log"; }
note_last() { printf '%s' "$1" > ${sh(noteOut)}; }
${seg}
`;
  // 外面的 E2E_BROWSER_NOTES 摘掉:要问的是**外层自己**有没有把路径交给子进程。
  const r = spawnSync("bash", ["-c", harness], { encoding: "utf8", env: envWithout("E2E_BROWSER_NOTES"), timeout: 30000 });
  assert.equal(r.status, 0, `外层 ⑥ 段在桩里跑挂了:rc=${r.status}\n${r.stderr}`);
  assert.ok(existsSync(noteOut), "外层 ⑥ 段没调 note_last ⇒ 这一段在汇总表里没有行");
  return readFileSync(noteOut, "utf8");
}

test("bt4 名字到得了人眼:外层汇总行写着「浏览器收容 N 次」+ 是哪几条(按真实点名计数,不数打印出来的字)", () => {
  // 🔴 为什么名字必须进汇总行:浏览器没关干净不改判定 ⇒ 外层走绿路径;默认跑法必有 2 条 SKIP
  //    ⇒ 外层 `rm -rf "$log_dir"` ⇒ 日志一定没了。泄漏又是偶发的,只给次数让人重跑去找,多半找不到。
  const d = tmp("ds-guardtest-bt4-");
  try {
    const notes = realBrowserNotes(d, ["a.e2e.mjs", "a.e2e.mjs", "b.e2e.mjs"]);
    // 假内层做真内层会做的两件事:helpers 往「外面给的点名簿」里写;汇总之后照内层格式打印点名块。
    // 打印块里**表头那行也含同一句话** —— 数打印出来的字就会多数(上一单的 F3)。
    const note = outerE2eNote(d, `
echo "== 汇总:3 PASS / 0 FAIL / 2 SKIP"
[ -n "\${E2E_BROWSER_NOTES:-}" ] && cat ${sh(notes)} >> "$E2E_BROWSER_NOTES"
echo "   ⚠️ 浏览器没走正常关闭(已自动收掉,只点名、不改判定):"
sed 's/^/     /' ${sh(notes)}
exit 0`);
    assert.ok(note.startsWith("3 PASS / 0 FAIL / 2 SKIP"), `汇总行把 e2e 段自己的数弄丢了:${note}`);
    assert.match(note, /浏览器收容 3 次/, `次数不对(真实 3 次):${note}`);
    assert.match(note, /a\.e2e\.mjs×2/, `没点名 a(两次):${note}`);
    assert.match(note, /b\.e2e\.mjs/, `没点名 b:${note}`);

    // 防误报:没人漏 ⇒ 汇总行不许出现「浏览器收容」。
    const d2 = tmp("ds-guardtest-bt4-clean-");
    try {
      const clean = outerE2eNote(d2, `echo "== 汇总:3 PASS / 0 FAIL / 2 SKIP"\nexit 0`);
      assert.equal(clean, "3 PASS / 0 FAIL / 2 SKIP", `没人漏却报了东西:${clean}`);
    } finally { rmSync(d2, { recursive: true, force: true }); }
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("bt5 内层尊重外面给的点名簿:给了 E2E_BROWSER_NOTES 就原样沿用;没给才落在自己的 ds-e2e-log-* 里", () => {
  // 🔴 bt4 的假内层替真内层「用了外面给的路径」;这条问真内层是不是真这么做。
  //    内层要是照旧无条件覆盖成自己的日志目录,外层读到的点名簿永远是空的 ⇒ 汇总行永远不报,而且不红。
  const seg = section(path.join(E2E_DIR, "run-all.sh"), 'log_dir="$(mktemp -d -t ds-e2e-log-', "# ── 隔离家目录");
  const d = tmp("ds-guardtest-bt5-");
  try {
    const script = `set -uo pipefail
${seg}
trap 'rm -rf "$log_dir"' EXIT
printf '%s\\n%s\\n' "$log_dir" "$E2E_BROWSER_NOTES"
`;
    const given = path.join(d, "given-notes.txt");
    const r1 = spawnSync("bash", ["-c", script], { encoding: "utf8", env: { ...process.env, E2E_BROWSER_NOTES: given } });
    assert.equal(r1.status, 0, `抽出来的那一截跑挂了:${r1.stderr}`);
    const [, got1] = r1.stdout.trim().split("\n");
    assert.equal(got1, given, "外面给了点名簿,内层却换成了自己的 ⇒ 外层汇总永远读到空的");

    const r2 = spawnSync("bash", ["-c", script], { encoding: "utf8", env: envWithout("E2E_BROWSER_NOTES") });
    assert.equal(r2.status, 0, `抽出来的那一截跑挂了:${r2.stderr}`);
    const [logDir2, got2] = r2.stdout.trim().split("\n");
    assert.ok(got2 && got2.startsWith(logDir2 + "/"), `单跑内层时点名簿不在内层自己的日志目录里:${got2}`);
  } finally { rmSync(d, { recursive: true, force: true }); }
});

test("ne11 回环判定不看报错文案:报错被翻译成别的语言时,lo 起不来照样拒跑", () => {
  // 🔴 由来:上一单 ne9 的 node 版拿 bash 报错**文本**匹配 `unreachable|不可达`;那段文字来自 libc 的
  //    strerror,换语言环境就不中 ⇒ lo 没起来也静默放行(实测:旧实现下场景照跑 rc=0)。
  //    本机没有 libc.mo,造不出真的非英文 locale ⇒ 用假 bash 把那一句翻掉来模拟。
  const d = tmp("ds-guardtest-ne11-"), fb = tmp("ds-guardtest-ne11-fakebin-");
  try {
    const realBash = spawnSync("bash", ["-c", "command -v bash"], { encoding: "utf8" }).stdout.trim();
    assert.ok(realBash.startsWith("/"), `找不到真 bash:${realBash}`);
    writeFileSync(path.join(fb, "ip"), "#!/bin/sh\nexit 1\n");
    // 只改写「连 127.0.0.1」那一种调用的报错;其余调用(自举、出口实测)原样交给真 bash。
    writeFileSync(path.join(fb, "bash"), `#!/bin/sh
case "$*" in
  *"/dev/tcp/127.0.0.1/"*) ${realBash} "$@" 2>&1 | sed 's/[Uu]nreachable/injoignable/g; s/不可达/injoignable/g' >&2; exit 1 ;;
esac
exec ${realBash} "$@"
`);
    chmodSync(path.join(fb, "ip"), 0o755);
    chmodSync(path.join(fb, "bash"), 0o755);
    const marker = path.join(d, "marker"), facts = path.join(d, "facts.json");
    const file = scenario(d, "probe.e2e.mjs", FACTS_BODY);
    const r = run(process.execPath, [file], {
      env: { GUARD_MARKER: marker, GUARD_FACTS: facts, PATH: `${fb}:${process.env.PATH}` },
    });
    assert.equal(r.status, 78, `报错换了语言,lo 起不来就放行了:rc=${r.status}\n${r.stderr}`);
    assert.match(r.stderr, /回环/, "拒跑了,但没点明是回环(lo)起不来");
    assert.equal(markerCount(marker), 0, "回环坏了还把场景跑了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

test("ne12 python 版回环起不来不许静默:假 ip ⇒ rc=78、横幅说是回环、脚本体没跑", () => {
  // 🔴 由来:上一单给 _no_egress.py 加了回环检查,但 ne9 只跑 node 场景、ne7 用真 ip(lo 总是起的)
  //    ⇒ 那段 python 一行没被问过。代码已在,本条写下去当场就绿;它的红由变异收据证明。
  const d = tmp("ds-guardtest-ne12-"), fb = tmp("ds-guardtest-ne12-fakebin-");
  try {
    writeFileSync(path.join(fb, "ip"), "#!/bin/sh\nexit 1\n");
    chmodSync(path.join(fb, "ip"), 0o755);
    const marker = path.join(d, "marker");
    const file = path.join(d, "probe.e2e.py");
    writeFileSync(file, `import os, sys
sys.path.insert(0, ${JSON.stringify(E2E_DIR)})
import _no_egress  # noqa: F401
open(os.environ["GUARD_MARKER"], "a").write("ran\\n")
`);
    const r = run(PY, [file], { env: { GUARD_MARKER: marker, PATH: `${fb}:${process.env.PATH}` } });
    assert.equal(r.status, 78, `python 版 lo 起不来却照跑:rc=${r.status}\n${r.stderr}`);
    assert.match(r.stderr, /无出口守卫/, "红了,但没说是守卫的事");
    assert.match(r.stderr, /回环/, "没点明是回环(lo)起不来");
    assert.equal(markerCount(marker), 0, "回环坏了还把脚本体跑了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(fb, { recursive: true, force: true }); }
});

test("bt2 正常 close 后退出:外层 TMPDIR 剩 0 个、不点名(防误报)", () => {
  const d = tmp("ds-guardtest-bt2-"), outer = tmp("ds-guardtest-bt2-tmp-");
  try {
    const notes = path.join(d, "notes.txt");
    const file = scenario(d, "probe-close.e2e.mjs", `
const browser = await H.launchBrowser();
const page = await browser.newPage();
await page.setContent("<p>x</p>");
await browser.close();
process.exit(0);`);
    const r = run(process.execPath, [file], { env: { TMPDIR: outer, TMP: outer, TEMP: outer, E2E_BROWSER_NOTES: notes } });
    assert.equal(r.status, 0, `场景没跑成:rc=${r.status}\n${r.stderr}`);
    assert.deepEqual(leftovers(outer), []);
    assert.doesNotMatch(r.stderr, /浏览器没走正常关闭/);
    assert.ok(!existsSync(notes) || readFileSync(notes, "utf8").trim() === "", "正常关闭也被点名了");
  } finally { rmSync(d, { recursive: true, force: true }); rmSync(outer, { recursive: true, force: true }); }
});

test("bt3 浏览器起不来:launchBrowser 抛错,外层 TMPDIR 不留 ds-e2e-browser-*", () => {
  const d = tmp("ds-guardtest-bt3-"), outer = tmp("ds-guardtest-bt3-tmp-"), home = tmp("ds-guardtest-bt3-home-");
  try {
    // 假 HOME 里放一个"chrome":一启动就退出 ⇒ launch 必失败(在建临时目录之后)
    const exe = path.join(home, ".cache", "ms-playwright", "chromium-99999", "chrome-linux64", "chrome");
    mkdirSync(path.dirname(exe), { recursive: true });
    writeFileSync(exe, "#!/bin/sh\nexit 1\n");
    chmodSync(exe, 0o755);
    const file = scenario(d, "probe-fail.e2e.mjs", `
try { await H.launchBrowser(); process.exit(3); } catch { process.exit(0); }`);
    const r = run(process.execPath, [file], { env: { TMPDIR: outer, TMP: outer, TEMP: outer, HOME: home } });
    assert.equal(r.status, 0, `假浏览器居然起来了、或场景崩了:rc=${r.status}\n${r.stderr}`);
    assert.deepEqual(readdirSync(outer).filter((n) => n.startsWith("ds-e2e-browser-")), [],
      "起不来的浏览器留下了它的临时目录");
  } finally {
    for (const x of [d, outer, home]) rmSync(x, { recursive: true, force: true });
  }
});
