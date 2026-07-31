// track opendesign-button-roles oracle(静态,总覆盖):
// 按位置命名的一次性按钮 class 必须**全部消失**,换成三档角色 class。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 为什么要有这份**静态**判据(而不是只靠 e2e):
// 九个使用点里有三个在「整理方案」流程里(CompanionColumn 336/343/373),
// 要造出待确认的整理方案才走得到 —— 行为判据够不着,而**够不着的地方正是最会被漏的地方**
// (0.64/0.65 连漏两轮的「没选中项目」那一支就是先例)。源码扫描是零成本的总覆盖。
//
// ⚠️ 这份判据只能证明"名字没了",证明不了"换对了角色"——后者靠 e2e 的逐点断言 +
// 主 agent 亲读 diff。别把它当充分条件。
//
// 跑法:node tests/test_button_roles.mjs
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "web", "src");

// 本单要清掉的三个(`.chat-btn` 的 `.primary` 修饰符跟着它一起走)。
// 范围外的一次性 class(.send-btn / .connect-workspace / .skip-btn / .icon-* 等)
// **刻意不列** —— 理由见 proposal.md 的 Non-goals,别在这里顺手扩大范围。
const BANNED = ["chat-btn", "go-link", "rail-expand-link"];

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(tsx?|css)$/.test(name)) out.push(p);
  }
  return out;
}

let failures = 0;
function expect(cond, label) {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++;
  console.error(`  FAIL: ${label}`);
}

const files = walk(SRC);
console.log(`== 扫 ${files.length} 个源文件`);

for (const cls of BANNED) {
  // 词边界匹配:`chat-btn` 不许误伤 `chat-btn-foo`,也不许放过 `.chat-btn:hover`。
  // 注释里提到它是允许的(删掉的规则原地留了说明) ⇒ 先剥掉注释再扫。
  const re = new RegExp(`(?<![\\w-])${cls}(?![\\w-])`);
  const hits = [];
  for (const f of files) {
    const raw = readFileSync(f, "utf8");
    const code = raw
      .replace(/\/\*[\s\S]*?\*\//g, "")   // /* ... */(css 与 tsx 通用)
      .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "") // JSX {/* ... */}
      .replace(/^\s*\/\/.*$/gm, "");      // 整行 //
    code.split("\n").forEach((line, i) => {
      if (re.test(line)) hits.push(`${f.slice(ROOT.length + 1)}:${i + 1}: ${line.trim()}`);
    });
  }
  expect(hits.length === 0,
    `\`${cls}\` 在源码里已彻底消失(实测 ${hits.length} 处${
      hits.length ? "\n      " + hits.join("\n      ") : ""})`);
}

// 反向前提:三档角色 class 必须还在(别"清理"成把角色 class 也删了)
const allCss = files.filter((f) => f.endsWith(".css")).map((f) => readFileSync(f, "utf8")).join("\n");
for (const role of ["btn-primary", "btn-secondary", "link-act"]) {
  expect(new RegExp(`\\.${role}\\s*\\{`).test(allCss), `角色 class \`.${role}\` 仍有定义`);
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
