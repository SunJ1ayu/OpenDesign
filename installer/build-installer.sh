#!/usr/bin/env bash
# 造 OpenDesign 的 Windows 安装器 —— 从零到一个可以发给业主的 .exe。
#
# 用法:installer/build-installer.sh <输出目录>
# 产出:<输出目录>/OpenDesign-Setup-<版本>.exe
#
# ## 为什么这条流水线长这样
#
# **在 Linux 上编 Windows 安装器**:`makensis` 是原生 Linux 程序,把 Ubuntu 的两个
# .deb 解到构建缓存里就能用,**零系统改动**。(Inno Setup 的 ISCC.exe 只有 Windows 版,
# 要靠 wine,而本机 wine 建不起 prefix —— 换工具的完整理由在 design.md。)
#
# **每一步都 fail closed**。这一单我一次也跑不了成品(编出来的 PE 只有 Windows 能执行),
# 可验证性只有"闸 + 业主真机一趟"。所以任何一道闸红了就停,不许"打印一行让人自己看见"：
#   闸 A/C  组包时的依赖闸(build-package.sh 自带,曾经真响过)
#   闸 B    成品结构(check-package.sh --app)
#   闸 静态  .nsi 的 20 条(check-installer.py static)
#   闸 成品  编出来的 exe:清单逐个文件对字节数(check-installer.py product)

set -euo pipefail

OUT="${1:?用法: build-installer.sh <输出目录>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SPIKE_DIR="$REPO/tracks/opendesign-windows-installer/spike"

# NSIS 的版本要**锁死**:同一份 .nsi 在不同版本的 makensis 上编出来的东西可以不一样,
# 而我没有第二台机器去发现这件事。(依赖不锁版本的代价本单已经付过一次:
# lark_oapi 1.5.5 vs 1.7.2 装完起不来。)
NSIS_VER="3.09-4ubuntu1"
NSIS_DEBS=("nsis_${NSIS_VER}_amd64.deb" "nsis-common_${NSIS_VER}_all.deb")
# 微软官方的 WebView2 引导程序(缺 WebView2 的机器上补装用;1.7MB,不含运行时本体)
WV2_URL="https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WV2_EXE="MicrosoftEdgeWebview2Setup.exe"

CACHE="$OUT/cache"
PKG="$OUT/pkg"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n🔴 %s\n' "$*" >&2; exit 1; }

mkdir -p "$CACHE"

# ---------------------------------------------------------------- 0. 版本号
# **唯一来源是 bin/ds_web.py 的 VERSION**。这里只读,不许手写 —— 名字里印错版本,
# 业主装完自报的版本就和我以为发出去的不是一回事。
APPVER="$(grep -oP '^VERSION = "\K[^"]+' "$REPO/bin/ds_web.py")"
[ -n "$APPVER" ] || die "从 bin/ds_web.py 读不出 VERSION"
say "0/6 版本 $APPVER"

# ---------------------------------------------------------------- 1. makensis
say "1/6 准备 NSIS $NSIS_VER(解到构建缓存,不动系统)"
NSIS_ROOT="$CACHE/nsis"
MAKENSIS="$NSIS_ROOT/usr/bin/makensis"
if [ ! -x "$MAKENSIS" ]; then
  mkdir -p "$CACHE/deb" "$NSIS_ROOT"
  ( cd "$CACHE/deb" && apt-get download nsis nsis-common >/dev/null 2>&1 ) \
    || die "下不动 nsis 的 deb(要能连 apt 源)"
  for d in "${NSIS_DEBS[@]}"; do
    [ -f "$CACHE/deb/$d" ] || die "拿到的不是锁定的版本:缺 $d"
    dpkg-deb -x "$CACHE/deb/$d" "$NSIS_ROOT"
  done
fi
[ -x "$MAKENSIS" ] || die "makensis 没解出来"
export NSISDIR="$NSIS_ROOT/usr/share/nsis"
GOT_VER="$("$MAKENSIS" -VERSION)"
echo "  makensis $GOT_VER"
[ "$GOT_VER" = "v${NSIS_VER%%-*}-${NSIS_VER##*ubuntu}" ] || echo "  (版本串 $GOT_VER,与包名 $NSIS_VER 对应)"

# ---------------------------------------------------------------- 2. 图标
say "2/6 图标(托盘 png + 程序 ico,同一份形状)"
python3 "$HERE/make-icon.py" "$REPO"

# ---------------------------------------------------------------- 3. payload
say "3/6 组包(出货形态:带外壳、不带考卷)"
bash "$SPIKE_DIR/build-package.sh" "$OUT" --app
[ -d "$PKG/python" ] || die "组包没产出 $PKG"

# ---------------------------------------------------------------- 4. 两个根文件
say "4/6 启动器 + WebView2 引导程序"
# 启动器:业主每天双击的那个 exe。编进 payload 根,跟着安装器一起铺下去。
# cwd 必须是 installer/ —— NSIS 的相对路径(`Icon "opendesign.ico"`)是按**当前目录**
# 解析的,不是按脚本所在目录。
# 输出路径**不用 `-X` 覆盖**:实测那条命令行会被脚本里的 OutFile 盖掉(编出来的东西
# 仍落在 installer/),而"编成功了但没落到该在的地方"是最容易被当成成功的一种失败。
# 老老实实编在原地再搬走 —— 少一个不确定的机制。
( cd "$HERE" && "$MAKENSIS" -NOCONFIG -INPUTCHARSET UTF8 -DAPPVER="$APPVER" launcher.nsi ) \
  > "$OUT/launcher-build.log" 2>&1 \
  || { tail -20 "$OUT/launcher-build.log"; die "启动器编不出来"; }
[ -f "$HERE/OpenDesign.exe" ] || die "启动器没编出来(installer/OpenDesign.exe 不在)"
mv "$HERE/OpenDesign.exe" "$PKG/OpenDesign.exe"
[ -f "$PKG/OpenDesign.exe" ] || die "启动器没落到 $PKG"
echo "  启动器 $(stat -c%s "$PKG/OpenDesign.exe") 字节"

# S1a 的账:两台机器上 WebView2 都在,但那只证明了那两台。不许赌。
if [ ! -f "$CACHE/$WV2_EXE" ]; then
  curl -fsSL -o "$CACHE/$WV2_EXE" "$WV2_URL" || die "下不动 WebView2 引导程序"
fi
# 微软会不定期更新这个文件 ⇒ **不锁哈希**(锁了每次都断),但把哈希记进构建日志,
# 出事时至少答得出"业主装的是哪一份"。
head -c2 "$CACHE/$WV2_EXE" | grep -q MZ || die "下回来的 WebView2 引导程序不是 PE"
cp "$CACHE/$WV2_EXE" "$PKG/$WV2_EXE"
echo "  WebView2 引导程序 $(stat -c%s "$PKG/$WV2_EXE") 字节  sha256=$(sha256sum "$PKG/$WV2_EXE" | cut -c1-16)…"

# ---------------------------------------------------------------- 5. 三道闸
say "5/6 闸:成品结构 + .nsi 静态"
bash "$SPIKE_DIR/check-package.sh" "$PKG" --app || die "闸 B:成品结构不合格"
python3 "$HERE/check-installer.py" static "$HERE/OpenDesign.nsi" --launcher "$HERE/launcher.nsi" \
  || die "静态闸:.nsi 不合格"

# ---------------------------------------------------------------- 6. 编安装器
say "6/6 编安装器"
# **cwd 必须是 payload 的父目录**:makensis -V4 打印的清单是相对路径,成品闸靠它
# 逐个文件对字节数。给绝对路径的话清单变成绝对路径,那条闸就对不上了。
cp "$HERE/OpenDesign.nsi" "$HERE/opendesign.ico" "$OUT/"
BUILDLOG="$OUT/makensis.log"
( cd "$OUT" && "$MAKENSIS" -NOCONFIG -INPUTCHARSET UTF8 -V4 \
    -DAPPVER="$APPVER" -DPAYLOAD="pkg" OpenDesign.nsi ) > "$BUILDLOG" 2>&1 \
  || { tail -30 "$BUILDLOG"; die "安装器编不出来"; }

EXE="$OUT/OpenDesign-Setup-${APPVER}.exe"
[ -f "$EXE" ] || die "编完没找到 $EXE"

python3 "$HERE/check-installer.py" product --exe "$EXE" --log "$BUILDLOG" \
  --payload "$PKG" --version "$APPVER" || die "成品闸:编出来的 exe 与 payload 对不上"

say "成了:$EXE($(stat -c%s "$EXE" | awk '{printf "%.1f MB", $1/1048576}'))"
echo "构建日志:$BUILDLOG"
