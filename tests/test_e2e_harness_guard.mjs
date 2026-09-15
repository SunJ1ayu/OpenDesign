// 判据:e2e 判据进程不许有外网出口 + 浏览器临时目录归测试自己收(track opendesign-e2e-no-egress-browser-tmp)。
// 编号权威表在 tracks/opendesign-e2e-no-egress-browser-tmp/design.md(前缀 ne / bt)。
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
