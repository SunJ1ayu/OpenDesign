// OpenDesign 自己的关卡策略：判卷面和高风险清单从本仓库推出来，字段对着 .aiwork/policy.json。
// 路径匹配只用 aiwork gate/decide.mjs 的 matchAny，不在这里另写一份。
// 关卡代码本身的判定在 SunJ1ayu/aiwork 的 tests/test_aiwork_gate*.mjs。
// 只读 AIWORK_CHECKOUT。没设，或那个目录里缺 gate/decide.mjs、gate/run.mjs，就失败。
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const aiwork = process.env.AIWORK_CHECKOUT;
const needed = ["gate/decide.mjs", "gate/run.mjs"];
const missing = aiwork ? needed.filter((name) => !existsSync(`${aiwork}/${name}`)) : needed;
if (!aiwork || missing.length) {
  throw new Error(`把 AIWORK_CHECKOUT 设成 aiwork 检出的路径。现在是 ${aiwork || "（没设）"}，没有 ${missing.join("、")}`);
}

const { decide, matchAny } = await import(pathToFileURL(`${aiwork}/gate/decide.mjs`).href);
const { validatePolicy } = await import(pathToFileURL(`${aiwork}/gate/run.mjs`).href);
const policy = JSON.parse(readFileSync(new URL("../.aiwork/policy.json", import.meta.url), "utf8"));

const HEAD = "a".repeat(40);

function review({ id = 1, login = "aiwork-review[bot]", type = "Bot", state = "COMMENTED", commit = HEAD, at = "2026-09-29T10:00:00Z", ...v }) {
  const block = {
    verdict: "PASS",
    head_sha: commit,
    model: "gpt-5-codex",
    family: "openai",
    completeness: "complete",
    files_read: ["web/src/a.ts"],
    ...v,
  };
  return { id, login, type, state, commit_id: commit, submitted_at: at, body: `评审意见……\n\n\`\`\`json\n${JSON.stringify(block)}\n\`\`\`\n` };
}
const approve = (commit = HEAD, at = "2026-09-29T11:00:00Z", state = "APPROVED") => ({
  id: 99, login: "SunJ1ayu", type: "User", state, commit_id: commit, submitted_at: at, body: "",
});

function facts(over = {}) {
  return {
    pr: { number: 10, state: "open", head_sha: HEAD },
    files: ["web/src/a.ts"],
    reviews: [review({})],
    ci: { state: "success", detail: "运行 1" },
    pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayuBoT"] },
    ...over,
  };
}
const run = (over) => decide(facts(over), policy);
const blocked = (r, rule) => {
  assert.equal(r.conclusion, "failure", `应拦下,实际 ${r.conclusion}:${r.title}`);
  if (rule) assert.match(r.summary, new RegExp(`❌ ${rule}`), `应因 ${rule} 拦下:\n${r.summary}`);
};

const ROOT = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, ROOT), "utf8");

test("策略:check 名是 aiwork-gate(已转真拦截);判卷面罩住 .github 与 .aiwork;Builder 只有机器账号;high 要 high_min_families 家", () => {
  assert.equal(policy.check_name, "aiwork-gate");
  assert.equal(policy.high_min_families, 2);
  for (const p of [".github/**", ".aiwork/**"]) assert.ok(policy.judging_surface.includes(p));
  assert.deepEqual(policy.builders, { SunJ1ayuBoT: "anthropic" });
  assert.equal(policy.reviewer_bot, "aiwork-review[bot]");
  validatePolicy(policy);
  const note = policy["_说明"].join("\n");
  assert.match(note, /gate\/README\.md/);
  assert.match(note, /high_min_families/);
  assert.match(note, /tests\/test_opendesign_gate_policy\.mjs/);
  assert.doesNotMatch(note, /两家/);
  assert.doesNotMatch(note, /\.github\/aiwork-gate\//);
  assert.doesNotMatch(note, /WORKFLOW-MIGRATION-PLAN/);
});

test("策略:普通测试文件不算判卷面", () => {
  assert.ok(!matchAny(policy.judging_surface, "tests/test_foo.py"), "普通测试文件不算判卷面");
});

test("策略:.github 下的关卡 workflow 和 .aiwork/policy.json 算判卷面(G2)", () => {
  for (const f of [".github/workflows/aiwork-gate.yml", ".github/workflows/aiwork-review-ping.yml", ".aiwork/policy.json"]) {
    assert.ok(matchAny(policy.judging_surface, f), f);
    blocked(run({ files: [f] }), "G2");
  }
});

// 前两条的根因是"清单靠手抄":这里改成从仓库本身推出应该在清单里的文件,以后新加的也跑不掉。
test("R6 总跑实际调用的测试框架文件都算判卷面(含 tests/tmpdir-leak-gate.sh)", () => {
  const harness = new Set([
    ...read("tests/run-all.sh").match(/tests\/[A-Za-z0-9_./-]+\.(?:sh|py|allow|mjs)/g),
    ...read("tests/e2e/run-all.sh").match(/tests\/[A-Za-z0-9_./-]+\.(?:sh|py|allow|mjs)/g),
    ...readdirSync(new URL("tests/e2e/", ROOT))
      // __pycache__ 是同一次 node --test 里导入 _no_egress.py 留下的字节码，不是框架文件
      .filter((f) => !/\.e2e\.(?:mjs|py)$/.test(f) && f !== "README.md" && f !== "__pycache__")
      .map((f) => `tests/e2e/${f}`),
    "tests/dead_assertions.allow",
  ]);
  const missing = [...harness].filter((f) => !matchAny(policy.judging_surface, f));
  assert.deepEqual(missing, [], `这些测试框架文件改了不用业主批准:${missing.join("、")}`);
  assert.ok(harness.has("tests/tmpdir-leak-gate.sh"), "量具:总跑确实调用 tmpdir-leak-gate.sh");
});

// high 清单从仓库推出(与 R6 判卷面同理,一处推导,不靠手抄):凡是
//   · bin/ 里碰机主密钥的文件(不限扩展名):ds_credential、apiKey / api_key、FOO_KEY 这类环境变量、口令、password、
//     ["token"] 写入,以及碰机主 nanobot 配置的 —— 那份配置里就是密钥、工具开关、模型端点。碰它有两种方式:
//     按路径打开它(代码里拼出配置路径),或按它的结构读写它(只有那份配置才有的键:modelPreset、model_presets、
//     mcpServers、restrictToWorkspace —— 比如 ds_model.py 决定写配置的人往哪个字段写);
//   · high 里的安装 / 启动脚本(.ps1)引用到的 bin/ 与 config/ 文件(首次配置时会跑、会合进用户配置的);
//   · nanobot 配置模板 config/nanobot.config*.jsonc(合进那份配置)
// 都必须在 high 里。历次评审漏掉的(ds_web.py、enable_webui.py、配置模板、bin/ds-nanobot、
// disable_builtin_file_tools.py)都是这里的量具。
const USER_SECRETS_RE = new RegExp([
  /\bds_credential\b|apiKey|api_key|\b[A-Z][A-Z0-9_]*_KEY\b|口令|[Pp]assword|\[["']token["']\]/.source,
  /["']~\/\.nanobot\/config\.json["']|["']\.nanobot["']\s*[,/]\s*["']config\.json["']/.source,
  /\bmodelPreset\b|\bmodel_presets\b|\bmcpServers\b|\brestrictToWorkspace\b/.source,
].join("|"));

test("high 清单从仓库推出:碰密钥 / 口令 / 机主 nanobot 配置的 bin 文件、安装脚本引用的 bin 与 config 文件、nanobot 配置模板,都在 high", () => {
  const keyFiles = readdirSync(new URL("bin/", ROOT), { withFileTypes: true })
    .filter((d) => d.isFile() && !d.name.endsWith(".pyc"))
    .map((d) => `bin/${d.name}`)
    .filter((f) => USER_SECRETS_RE.test(read(f)));
  const launchers = readdirSync(new URL("bin/", ROOT)).filter((f) => f.endsWith(".ps1")).map((f) => `bin/${f}`).filter((f) => matchAny(policy.high, f));
  const referenced = [...new Set(launchers.flatMap((f) => [...read(f).matchAll(/\b(bin|config)[\\/]([A-Za-z0-9_.-]+)/g)].map((m) => `${m[1]}/${m[2]}`)))]
    .filter((p) => existsSync(new URL(p, ROOT)));
  const templates = readdirSync(new URL("config/", ROOT)).filter((f) => /^nanobot\.config.*\.jsonc$/.test(f)).map((f) => `config/${f}`);
  for (const f of ["bin/ds_credential.py", "bin/ds_web.py", "bin/ds_shell_core.py", "bin/ds_provision.py", "bin/enable_webui.py", "bin/ds-nanobot", "bin/set_model.py", "bin/disable_builtin_file_tools.py", "bin/ds_model.py"]) {
    assert.ok(keyFiles.includes(f), `量具:扫得到碰密钥 / 口令 / 机主 nanobot 配置的 ${f}`);
  }
  for (const f of ["bin/ds_tools.py", "bin/ds_sessions.py", "bin/ds_mcp.py", "bin/ds_common.py"]) {
    assert.ok(!keyFiles.includes(f), `对照:${f} 只在提示文字里提到那份配置 / 只用 workspace,不算`);
  }
  assert.ok(launchers.includes("bin/install.ps1"), "量具:安装脚本本身在 high");
  for (const f of ["bin/enable_webui.py", "bin/ds_merge_config.py", "config/nanobot.config.windows.jsonc"]) {
    assert.ok(referenced.includes(f), `量具:install.ps1 引用 ${f}`);
  }
  assert.ok(templates.length >= 2, "量具:Windows 与 Linux 两份模板");
  const missing = [...new Set([...keyFiles, ...referenced, ...templates])].filter((f) => !matchAny(policy.high, f));
  assert.deepEqual(missing, [], `这些碰密钥 / 首次配置的文件改了只要一家 PASS:${missing.join("、")}`);
  for (const f of ["bin/ds_web.py", "bin/enable_webui.py", "config/nanobot.config.windows.jsonc", "bin/ds-nanobot", "bin/disable_builtin_file_tools.py", "bin/ds_model.py"]) {
    blocked(run({ files: [f], reviews: [review({})] }), "G6");
  }
  assert.ok(!matchAny(policy.high, "config/taxonomy.default.json"), "对照:分类表是产品数据,不算 high");
});

// 给写代码的 agent 的指令文件(评审和修改怎么做、听谁的)和评审规则是一回事:Builder 改了它们,就改了约束自己的规则。
// 这一类从仓库推出:Claude Code 自动读任意层级的 CLAUDE.md / CLAUDE.local.md 和 .claude/ 下的设置、钩子、skill;
// Codex 读 AGENTS.md / AGENTS.override.md(评审腿在仓库根跑,所以策略罩的是根目录那份;子目录里再冒出一份,这里会红,逼着定它算不算)。
// workspace/AGENTS.md 不算:那是装到用户电脑上给产品助手看的契约,产品数据,走普通评审。
const AGENT_INSTRUCTIONS_RE = /(^|\/)CLAUDE(\.local)?\.md$|(^|\/)AGENTS(\.override)?\.md$|^\.claude\//;
const PRODUCT_CONTRACT = "workspace/AGENTS.md";

test("R30 给写代码的 agent 的指令文件(AGENTS.md、CLAUDE.md、.claude/)都算判卷面,改了要业主批准(G2)", () => {
  const tracked = execFileSync("git", ["ls-files"], { cwd: new URL(".", ROOT), encoding: "utf8" }).split("\n").filter(Boolean);
  const found = tracked.filter((f) => AGENT_INSTRUCTIONS_RE.test(f) && f !== PRODUCT_CONTRACT);
  for (const f of ["AGENTS.md", "CLAUDE.md"]) assert.ok(found.includes(f), `量具:扫得到 ${f}`);
  assert.ok(tracked.includes(PRODUCT_CONTRACT), "量具:产品契约还在原处");
  const missing = found.filter((f) => !matchAny(policy.judging_surface, f));
  assert.deepEqual(missing, [], `这些 agent 指令文件改了不用业主批准:${missing.join("、")}`);
  for (const f of ["CLAUDE.local.md", "web/CLAUDE.md", "AGENTS.override.md", ".claude/settings.json", ".claude/skills/steward/SKILL.md"]) {
    assert.ok(matchAny(policy.judging_surface, f), `以后加的 ${f} 也要罩住`);
  }
  assert.ok(!matchAny(policy.judging_surface, PRODUCT_CONTRACT), "对照:产品契约不算判卷面");
  for (const f of ["AGENTS.md", "CLAUDE.md", ".claude/settings.json"]) {
    blocked(run({ files: [f] }), "G7");
    assert.equal(run({ files: [f], reviews: [review({}), approve()] }).conclusion, "success", `${f}:业主批准后放行`);
  }
});
