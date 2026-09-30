import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_BASE = "https://github.com/SunJ1ayu/OpenDesign/releases/download";
const installerName = (version) => `OpenDesign-${version}-electron-setup.exe`;

function field(text, name) {
  const match = text.match(new RegExp(`^\\s*(?:- )?${name}: (.+)$`, "m"));
  return match ? match[1].trim().replace(/^['"]|['"]$/g, "") : null;
}

export function rewriteLatestYml(text, version, base = DEFAULT_BASE) {
  if (field(text, "version") !== version) throw new Error("latest.yml 的版本与发布版本不一致");
  const name = installerName(version);
  const currentUrl = field(text, "url");
  const currentPath = field(text, "path");
  if (!currentUrl || !currentPath || !currentUrl.endsWith(name) || !currentPath.endsWith(name)) {
    throw new Error(`latest.yml 的安装包名必须是 ${name}`);
  }
  const absolute = `${base.replace(/\/$/, "")}/v${version}/${name}`;
  return text
    .replace(/^(\s*-\s*url:\s*).+$/m, `$1${absolute}`)
    .replace(/^(path:\s*).+$/m, `$1${absolute}`);
}

export function sha512Base64(buffer) {
  return createHash("sha512").update(buffer).digest("base64");
}

export function verifyFeed(text, installer) {
  const expectedSha = field(text, "sha512");
  const expectedSize = Number(field(text, "size"));
  if (!expectedSha) return { ok: false, reason: "latest.yml 缺少 sha512" };
  if (!Number.isFinite(expectedSize)) return { ok: false, reason: "latest.yml 缺少 size" };
  if (installer.length !== expectedSize) return { ok: false, reason: `大小不一致：${installer.length} != ${expectedSize}` };
  const actual = sha512Base64(installer);
  if (actual !== expectedSha) return { ok: false, reason: "sha512 不一致" };
  return { ok: true, reason: "" };
}

// target:tag 打在哪个提交上,必须给构建用的那个提交。不给时 gh 把 tag 打在发布那一刻的 main 最新提交上 ——
// 打包到发布之间 main 前进了,tag 就指向没打进包里的代码。没有哪种发法可以不管这个,所以不给就不生成命令。
export function ghReleaseCommand({ version, installer, blockmap, latestYml, latestYmlText, target }) {
  const name = installerName(version);
  if (!installer.endsWith(name) || !blockmap.endsWith(`${name}.blockmap`)) throw new Error("发布资产名与版本不一致");
  if (basename(latestYml) !== "latest.yml") throw new Error("更新清单资产名必须是 latest.yml");
  const rewritten = rewriteLatestYml(latestYmlText, version);
  if (rewritten !== latestYmlText) throw new Error("latest.yml 还没有改写成带版本的绝对地址");
  if (!/^[0-9a-f]{40}$/.test(target ?? "")) throw new Error("--target 要给构建用的那个提交(完整的 40 位提交号)");
  return [
    "release", "create", `v${version}`,
    installer, blockmap, latestYml,
    "--repo", "SunJ1ayu/OpenDesign",
    "--title", `OpenDesign ${version}`,
    "--generate-notes",
    "--target", target,
  ];
}

function shellQuote(value) {
  return /^[A-Za-z0-9_./:@+-]+$/.test(value) ? value : `'${value.replaceAll("'", `'\\''`)}'`;
}

async function main(argv) {
  const [command, ...args] = argv;
  if (command === "verify" && args.length === 2) {
    const result = verifyFeed(await readFile(args[0], "utf8"), await readFile(args[1]));
    if (!result.ok) throw new Error(result.reason);
    console.log("latest.yml 的 sha512 与 size 均和安装包一致");
    return;
  }
  if (command === "rewrite" && args.length >= 3) {
    const [input, output, version, flag, base] = args;
    if (flag && flag !== "--base") throw new Error("只支持 --base URL");
    if (flag && !base) throw new Error("--base 后缺 URL");
    const rewritten = rewriteLatestYml(await readFile(input, "utf8"), version, base || DEFAULT_BASE);
    await writeFile(output, rewritten, "utf8");
    console.log(`已改写 ${output}`);
    return;
  }
  if (command === "gh-command" && args.length >= 4) {
    const [version, installer, blockmap, latestYml, ...rest] = args;
    let target;
    let run = false;
    for (let i = 0; i < rest.length; i++) {
      if (rest[i] === "--target" && rest[i + 1]) target = rest[++i];
      else if (rest[i] === "--run") run = true;
      else throw new Error(`不认识的参数 ${rest[i]}`);
    }
    const commandArgs = ghReleaseCommand({
      version, installer, blockmap, latestYml, target,
      latestYmlText: await readFile(latestYml, "utf8"),
    });
    console.log(["gh", ...commandArgs].map(shellQuote).join(" "));
    // --run:发版 workflow 用。直接执行上面这条(不经 shell),保证真正执行的就是 r8 / r9 钉住的那组实参。
    if (run) execFileSync("gh", commandArgs, { stdio: "inherit" });
    return;
  }
  throw new Error("用法：verify <latest.yml> <安装包> | rewrite <入> <出> <版本> [--base URL] | gh-command <版本> <安装包> <blockmap> <latest.yml> --target 提交号 [--run]");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error.message || error);
    process.exitCode = 1;
  });
}
