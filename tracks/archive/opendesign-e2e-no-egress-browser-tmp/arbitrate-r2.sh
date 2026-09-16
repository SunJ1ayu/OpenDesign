#!/bin/bash
# 第 2 轮仲裁:DeepSeek BLOCK 各条在 HEAD 上的复现(只读,不改仓内文件)
set -u
cd "$(git rev-parse --show-toplevel)"
w=$(mktemp -d); trap 'rm -rf "$w"' EXIT
echo "== F2 bt4 是否被注释满足(删掉两行计数代码、保留注释,按 bt4 原样判法)"
node -e '
const fs=require("fs");const MARK="浏览器没走正常关闭";
const bt4=o=>{const s=o.slice(o.indexOf("⑥ e2e 总跑"));const n=s.indexOf("note_last"),m=s.indexOf(MARK);return m>=0&&m<n;};
const o=fs.readFileSync("tests/run-all.sh","utf8");
const k=o.split("\n").filter(l=>!l.startsWith("_bn=")&&!l.startsWith("[ \"$_bn\""));
console.log("  HEAD 实现: bt4 =",bt4(o));
console.log("  删掉",o.split("\n").length-k.length,"行计数代码: bt4 =",bt4(k.join("\n")));'
echo "== F3 计数:用两处真实代码块,喂 1 条点名"
printf 'x.e2e.mjs: 浏览器没走正常关闭,留下 org.chromium.Chromium.AbC123(已收掉)\n' > "$w/notes"
{ echo "== 汇总:40 PASS / 0 FAIL / 2 SKIP"
  E2E_BROWSER_NOTES="$w/notes" bash -c "$(sed -n '/^if \[ -s "\$E2E_BROWSER_NOTES" \]; then/,/^fi/p' tests/e2e/run-all.sh)"; } > "$w/seg"
_l="$w/seg"; eval "$(sed -n '/^_sum=\$(grep -m1/,/^\[ "\$_bn" -gt 0 \]/p' tests/run-all.sh)"
echo "  汇总行 => $_sum"; echo "  真实发生 1 次"
echo "== F4 bash /dev/tcp 的报错文本出处(bash 自带 vs libc strerror)"
echo "  bash 二进制含 unreachable: $(strings "$(command -v bash)" | grep -ci unreachable)"
echo "  libc 含 'Network is unreachable': $(strings /usr/lib/x86_64-linux-gnu/libc.so.6 | grep -c 'Network is unreachable')"
echo "== F7 泄漏闸数不数文件(MiMo 说只数目录)"
d=$(mktemp -d); : > "$d/ds-e2e-noegress-1.started"
echo "  find 数法(同闸第 121 行): $(find "$d" -mindepth 1 -maxdepth 1 -printf '%f\n' | wc -l) 个"; rm -rf "$d"
echo "== 证据缺口:本 track 证据里外层 tests/run-all.sh 真打印过的汇总表头行数"
# 匹配外层真正打印的那一整行(带 ════),别用裸词 —— 本脚本的标题也含那四个字,会数到自己的旧收据。
echo "  $(cat tracks/opendesign-e2e-no-egress-browser-tmp/evidence/*.txt | grep -c '^════ 总跑汇总 ════$')"
