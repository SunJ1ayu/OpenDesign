#!/usr/bin/env bash
# 组包流水线 —— 从零装配一个 Windows 免装包(embeddable Python + 全部依赖 + ds 文件)。
#
# 为什么这个脚本必须存在(2026-08-13 补的账):
# S0 那次组包是**手工做的**,步骤只活在一段散文里,素材(wheels / embeddable python /
# 成品包)事后一个不剩。更要命的是真机第一跑抓到的 F1 ——「跨平台解析依赖时环境标记被
# 静默丢掉」—— 是**流水线级**的 bug,而那条流水线不在仓里 ⇒ 那个修复没有任何载体,
# 下次重建包会原样再犯一次。
#
# 所以这里的规矩是:**每一个曾经栽过的坑,都在这里变成一道会失败的闸**,而不是一行注释。
#   闸 A:Windows 条件依赖漏没漏(win-deps-audit.py,fail closed)
#   闸 B:成品结构合不合格(check-package.sh,fail closed)
#   闸 C:只允许 Windows 轮子进包(--only-binary + --platform,任何源码包直接失败)
#
# 用法:build-package.sh <输出目录> [--with-shell]
#   --with-shell:额外装桌面外壳依赖(S1a 探路包用;S0 不需要)
#
# 产出:<输出目录>/pkg/ 与 <输出目录>/OpenDesign-spike.zip

set -euo pipefail

OUT="${1:?用法: build-package.sh <输出目录> [--with-shell]}"
WITH_SHELL=0
[ "${2:-}" = "--with-shell" ] && WITH_SHELL=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"          # design-studio 仓根

PY_VER=3.12.10
PY_ZIP="python-${PY_VER}-embed-amd64.zip"
PY_URL="https://www.python.org/ftp/python/${PY_VER}/${PY_ZIP}"

# 与 bin/install.ps1:69 同一份 pin —— **唯一来源在那里**,这里若与它不一致,
# 组出来的包就和业主真机上装的不是一回事。
PINS=(nanobot-ai==0.2.2 mcp==1.28.1 firecrawl-anydoc==0.1.6)
# 外壳依赖(S1a 才用):裁决 pywebview 路线跑不跑得起来
SHELL_PINS=(pywebview==5.4 pystray==0.19.5 pythonnet==3.0.5)

PKG="$OUT/pkg"
CACHE="$OUT/cache"
SP="$PKG/python/Lib/site-packages"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n🔴 %s\n' "$*" >&2; exit 1; }

mkdir -p "$CACHE"
rm -rf "$PKG"; mkdir -p "$PKG"

# ---------------------------------------------------------------- 1. 运行时
say "1/6 免装 Python ${PY_VER}"
if [ ! -f "$CACHE/$PY_ZIP" ]; then
  curl -fL --retry 3 -o "$CACHE/$PY_ZIP" "$PY_URL" || die "下不动 $PY_URL"
fi
mkdir -p "$PKG/python"
unzip -q "$CACHE/$PY_ZIP" -d "$PKG/python"

# `._pth` 是全包最脆的一环,两处都必须改,而且**都是曾经栽过的坑**:
#   ① 默认注释掉 `import site` ⇒ 不放开就加载不到 site-packages
#   ② `._pth` 存在时 **PYTHONPATH 被忽略**,而 ds 的模块之间是平级 import
#      (ds_web.py 直接 import ds_common)⇒ ds\bin 必须写死进来,环境变量注入无效
PTH="$PKG/python/python312._pth"
[ -f "$PTH" ] || die "找不到 $PTH(embeddable 包结构变了?)"
{
  echo "python312.zip"
  echo "."
  echo "Lib\\site-packages"
  echo "..\\ds\\bin"
  # pywin32 靠一个 .pth 文件把 win32\lib 挂上路径,而 embeddable + ._pth 下 .pth 会不会
  # 被处理,我在 Linux 上验不了 ⇒ 写死进来,不赌(闸 B 会查这一条)。
  echo "Lib\\site-packages\\win32"
  echo "Lib\\site-packages\\win32\\lib"
  echo "Lib\\site-packages\\Pythonwin"
  echo "import site"
} > "$PTH"

# ---------------------------------------------------------------- 2. 依赖
say "2/6 装配依赖(仅 Windows 轮子,源码包一律拒收)"
mkdir -p "$SP"
# --only-binary=:all: = 闸 C:任何需要现场编译的源码包直接让这一步失败,
# 而不是让业主的机器上缺个编译器才炸。
python3 -m pip install \
  --target "$SP" \
  --platform win_amd64 \
  --python-version "${PY_VER%.*}" \
  --only-binary=:all: \
  --no-compile \
  --quiet \
  "${PINS[@]}" || die "依赖装配失败(闸 C:很可能有包没有 Windows 轮子)"

if [ "$WITH_SHELL" = 1 ]; then
  say "2b/6 外壳依赖(S1a)"
  python3 -m pip install \
    --target "$SP" --platform win_amd64 --python-version "${PY_VER%.*}" \
    --only-binary=:all: --no-compile --quiet \
    "${SHELL_PINS[@]}" || die "外壳依赖装配失败"
fi

# ---------------------------------------------------------------- 3. 闸 A
say "3/6 闸 A:Windows 条件依赖有没有被静默丢掉(F1 的机械版)"
# 这是本脚本存在的最大理由。pip 用 --platform 挑轮子,但**环境标记是拿当前解释器判的**
# ⇒ 在 Linux 上解析,`sys_platform == 'win32'` 的依赖整批消失,且**一声不响**。
# 补法要机械:让 audit 自己报出缺哪些,补完再扫一遍,**两遍都得干净**才放行。
if ! python3 "$HERE/win-deps-audit.py" "$SP" > "$OUT/audit-1.txt" 2>&1; then
  MISSING="$(grep -oP '(?<=--only-binary=:all: ).*' "$OUT/audit-1.txt" | tail -1)"
  [ -n "$MISSING" ] || { cat "$OUT/audit-1.txt"; die "闸 A 红了但没解析出缺失清单"; }
  echo "  缺:$MISSING —— 补装"
  # shellcheck disable=SC2086
  python3 -m pip install --target "$SP" --platform win_amd64 \
    --python-version "${PY_VER%.*}" --only-binary=:all: --no-compile --quiet $MISSING \
    || die "补装 Windows 专属依赖失败"
  python3 "$HERE/win-deps-audit.py" "$SP" > "$OUT/audit-2.txt" 2>&1 \
    || { cat "$OUT/audit-2.txt"; die "闸 A:补完还是缺(别手工绕过,先弄明白为什么)"; }
  echo "  补装后复扫:干净"
else
  echo "  一遍过,没有漏网的 Windows 条件依赖"
fi

# ---------------------------------------------------------------- 4. ds 文件
say "4/6 ds 文件"
mkdir -p "$PKG/ds/bin" "$PKG/ds/config" "$PKG/ds/web"
cp "$REPO"/bin/*.py "$PKG/ds/bin/"
cp "$REPO"/config/nanobot.config.windows.jsonc "$PKG/ds/config/"
cp -r "$REPO/web/dist" "$PKG/ds/web/"
[ -d "$REPO/workspace" ] && cp -r "$REPO/workspace" "$PKG/ds/"
cp "$HERE/spike.py" "$PKG/spike.py"

# 版本号锚:判据要拿它跟 ds-web 自报的版本对一遍(两边对不上 = 包里混了两个版本的代码)。
# **单一来源是 bin/ds_web.py 的 VERSION**,这里只是抄过去,不许手写。
DSVER="$(grep -oP '^VERSION\s*=\s*"\K[^"]+' "$REPO/bin/ds_web.py")"
[ -n "$DSVER" ] || die "从 bin/ds_web.py 读不出 VERSION"
printf '%s\n' "$DSVER" > "$PKG/ds/版本号.txt"
echo "  ds-web 版本 $DSVER"

# ---------------------------------------------------------------- 5. 入口
say "5/6 入口 跑一下.bat(CRLF)"
# CRLF 是硬要求:LF 结尾的 .bat 在 cmd.exe 下会有诡异行为。
# **不接管道** —— 管道会吃掉 rc,业主看到的"跑完了"可能是假的(本机为这条记过三次账)。
printf '@echo off\r\nchcp 65001 >nul\r\ncd /d "%%~dp0"\r\npython\\python.exe spike.py\r\necho.\r\necho ==== 跑完了,把上面的内容截图发回来 ====\r\npause\r\n' \
  > "$PKG/跑一下.bat"

# ---------------------------------------------------------------- 6. 闸 B + 出 zip
say "6/6 闸 B:成品结构检查"
bash "$HERE/check-package.sh" "$PKG" || die "闸 B:成品结构不合格"

ZIP="$OUT/OpenDesign-spike.zip"
rm -f "$ZIP"
( cd "$PKG" && zip -qr "$ZIP" . )
unzip -qt "$ZIP" || die "出 zip 后回读校验失败"

printf '\n\033[1m✅ 组包完成\033[0m\n'
printf '  包目录: %s (%s)\n' "$PKG" "$(du -sh "$PKG" | cut -f1)"
printf '  zip   : %s (%s)\n' "$ZIP" "$(du -sh "$ZIP" | cut -f1)"
printf '  外壳依赖: %s\n' "$([ "$WITH_SHELL" = 1 ] && echo '已含(S1a)' || echo '未含(S0 形态)')"
