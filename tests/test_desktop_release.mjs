// 发布那一步改写 latest.yml(track opendesign-electron-shell,T3;主 agent 亲写,判据先单独 commit)。
// 跑法:node --test tests/test_desktop_release.mjs
//
// 由来(探路第七~九跑):electron-updater 找旧版 blockmap 的地址 = 新安装包地址**把路径里所有新版本号
// 换成旧版本号**(electron-updater providers/Provider.js)。GitHub 的 `releases/latest/download/` 下只有
// 最新 release 的资产 ⇒ 旧 blockmap 404 ⇒ 退整包 158MB。`previousBlockmapBaseUrlOverride` 第八跑证伪
// (只换主机不换路径)。第九跑证实的做法:发布时把 latest.yml 里安装包地址写成
// `…/releases/download/v<新版>/OpenDesign-<新版>-electron-setup.exe` 绝对地址 ⇒ 换号后正好落在旧版自己那个
// release 下(实下 1.06MB / 165.7MB)。
// 这一步是**人工发布流程里的一环**,漏做、做错都不报错,只会让每次更新安静地变成整包 —— 所以钉住。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const { rewriteLatestYml, sha512Base64, verifyFeed, ghReleaseCommand } = await import("../desktop/scripts/release-feed.mjs");

const BASE = "https://github.com/SunJ1ayu/OpenDesign/releases/download";
const SHA = "q1w2e3r4t5y6u7i8o9p0ZZZZzzzz0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRS==";
// electron-builder 26 的 latest.yml 原样形状(探路第九跑产物)
const LATEST = `version: 0.98.11
files:
  - url: OpenDesign-0.98.11-electron-setup.exe
    sha512: ${SHA}
    size: 165676277
path: OpenDesign-0.98.11-electron-setup.exe
sha512: ${SHA}
releaseDate: '2026-09-22T07:20:11.000Z'
`;

function field(yml, key) {
  const m = yml.match(new RegExp(`^\\s*(?:- )?${key}: (.+)$`, "m"));
  return m && m[1].trim();
}

test("r1 url 与 path 都改成带版本号的 release 绝对地址", () => {
  const out = rewriteLatestYml(LATEST, "0.98.11");
  const want = `${BASE}/v0.98.11/OpenDesign-0.98.11-electron-setup.exe`;
  assert.equal(field(out, "url"), want);
  assert.equal(field(out, "path"), want);
});

test("r2 sha512、size、version、releaseDate 一个字都不动", () => {
  const out = rewriteLatestYml(LATEST, "0.98.11");
  const keep = (y) => y.split("\n").filter((l) => !/^\s*(- )?(url|path):/.test(l)).join("\n");
  assert.equal(keep(out), keep(LATEST), "改写碰了校验和或别的字段 ⇒ 更新器校验失败、整次更新作废");
});

test("r3 🔴 换号之后正好是旧版自己那个 release 里的 blockmap(第九跑的机制,跳版也成立)", () => {
  const out = rewriteLatestYml(LATEST, "0.98.11");
  const url = new URL(field(out, "url"));
  for (const old of ["0.98.10", "0.98.9"]) {
    // electron-updater Provider.js 的做法:新安装包地址的 pathname 里所有新版本号换成旧版本号,再加 .blockmap
    const oldMap = `${url.origin}${url.pathname.split("0.98.11").join(old)}.blockmap`;
    assert.equal(oldMap, `${BASE}/v${old}/OpenDesign-${old}-electron-setup.exe.blockmap`);
  }
});

test("r4 已经改过的再改一遍不变(发布时手滑跑两次不许拼出两段前缀)", () => {
  const once = rewriteLatestYml(LATEST, "0.98.11");
  assert.equal(rewriteLatestYml(once, "0.98.11"), once);
});

test("r5 版本对不上就拒绝(拿错了 latest.yml ⇒ 旧版会被指去装错的东西)", () => {
  assert.throws(() => rewriteLatestYml(LATEST, "0.98.12"));
  assert.throws(() => rewriteLatestYml(LATEST.replace(/electron-setup/g, "Setup"), "0.98.11"),
    "安装包名不是 OpenDesign-<版本>-electron-setup.exe ⇒ 不认");
});

test("r6 sha512 校验:和安装包逐字节对得上才放行,换过一个字节就抓到", () => {
  const buf = Buffer.from("假装是一个安装包 " + "x".repeat(1000));
  const sha = createHash("sha512").update(buf).digest("base64");
  assert.equal(sha512Base64(buf), sha);
  const yml = LATEST.split(SHA).join(sha).replace(/size: \d+/, `size: ${buf.length}`);
  assert.equal(verifyFeed(yml, buf).ok, true);
  const tampered = Buffer.from(buf);
  tampered[3] ^= 1;
  const r = verifyFeed(yml, tampered);
  assert.equal(r.ok, false);
  assert.ok(r.reason, "拒绝要说理由");
  const wrongSize = verifyFeed(yml.replace(/size: \d+/, "size: 1"), buf);
  assert.equal(wrongSize.ok, false, "size 对不上也要拒");
});

test("r7 云 Windows 判据用同一个函数,只换主机前缀(替身源 http://127.0.0.1:8900/download)", () => {
  const out = rewriteLatestYml(LATEST, "0.98.11", "http://127.0.0.1:8900/download");
  assert.equal(field(out, "url"), "http://127.0.0.1:8900/download/v0.98.11/OpenDesign-0.98.11-electron-setup.exe");
  assert.equal(rewriteLatestYml(out, "0.98.11", "http://127.0.0.1:8900/download"), out);
});

test("r8 🔴 发布命令由工具生成:正式 release、tag v<版本>、恰好三样资产、latest.yml 必须是改写过的(攻题 #15/#23)", () => {
  const dir = "dist";
  const files = {
    installer: `${dir}/OpenDesign-0.98.11-electron-setup.exe`,
    blockmap: `${dir}/OpenDesign-0.98.11-electron-setup.exe.blockmap`,
    latestYml: "feed/latest.yml",
  };
  const argv = ghReleaseCommand({ version: "0.98.11", ...files, latestYmlText: rewriteLatestYml(LATEST, "0.98.11") });
  assert.deepEqual(argv.slice(0, 3), ["release", "create", "v0.98.11"]);
  for (const bad of ["--prerelease", "--draft"]) {
    assert.ok(!argv.includes(bad), `${bad} ⇒ releases/latest/download 看不见它,旧版永远「已是最新」`);
  }
  // 复核:先滤成「已知三个路径」再比 ⇒ 多带一个别的文件不会红。这里按扩展名认出**所有**像资产的实参(gh 的 `文件#显示名` 也算)。
  const assets = argv.slice(3).filter((a) => !a.startsWith("-") && /\.(exe|blockmap|ya?ml|zip|7z|msi|nupkg)(#.*)?$/i.test(a));
  assert.deepEqual(assets.sort(), Object.values(files).sort(), "资产要恰好三样:安装包 + blockmap + 改写过的 latest.yml");
  const r = argv.indexOf("--repo");
  if (r >= 0) assert.equal(argv[r + 1], "SunJ1ayu/OpenDesign");
  assert.throws(() => ghReleaseCommand({ version: "0.98.11", ...files, latestYmlText: LATEST }),
    "没改写的 latest.yml 发出去 ⇒ 每次更新都退整包 158MB");
  assert.throws(() => ghReleaseCommand({ version: "0.98.12", ...files, latestYmlText: rewriteLatestYml(LATEST, "0.98.11") }),
    "版本对不上还给命令 ⇒ 发出去的 tag 和包不是一版");
});
