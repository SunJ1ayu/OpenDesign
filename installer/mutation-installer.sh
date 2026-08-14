#!/usr/bin/env bash
# 红检(变异测试)—— 证明 installer/check-installer.py 的每一条闸都咬得动。
#
# 这份红检比别处更要紧:安装器我**一次也跑不了**(编出来的 PE 只有 Windows 能执行),
# 可验证性只有"静态闸 + 业主真机一趟"两处。静态闸要是瞎的,就只剩业主一个人替我兜底。
#
# 规矩同 tests/mutation-ds-shell-core.sh:
#   1. 变异**被测对象**(两份 .nsi),不是判据;
#   2. 每条变异指定靶子,必须是**那一条**闸红;
#   3. 跑完原样还回去并核哈希。
#
# 用法:installer/mutation-installer.sh
# 退出码:0 = 全咬住  1 = 有漏网  2 = 现场问题

set -u
cd "$(dirname "$0")/.."
NSI=installer/OpenDesign.nsi
LAU=installer/launcher.nsi
GATE="python3 installer/check-installer.py static $NSI --launcher $LAU"
WORK="$(mktemp -d)"
B1="$(sha256sum "$NSI" | cut -d' ' -f1)"
B2="$(sha256sum "$LAU" | cut -d' ' -f1)"
cp "$NSI" "$WORK/nsi.orig"; cp "$LAU" "$WORK/lau.orig"

restore() { cp "$WORK/nsi.orig" "$NSI"; cp "$WORK/lau.orig" "$LAU"; }
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

# mutate_and_expect <id> <靶子前缀> <文件> <旧1> <新1> [<旧2> <新2> ...]
#
# 支持多点是必须的:有的契约由**两道防线共同**保证(比如"装坏了要弹中文"在两处各有一个
# MessageBox),只拆其中一道本就不该红 —— 那样的漏网不是闸瞎,是变异没打在契约上。
mutate_and_expect() {
  local id="$1" target="$2" file="$3"; shift 3
  local out="$WORK/mut-$id.txt"
  restore
  python3 - "$file" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
args = sys.argv[2:]
if len(args) % 2:
    sys.exit("旧/新必须成对")
for old, new in zip(args[0::2], args[1::2]):
    if old not in s:
        sys.exit(f"变异锚点找不到: {old!r}")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
PYEOF
  $GATE > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 闸全绿:这条变异下它是瞎的(靶子 $target)"
    fail=$((fail+1))
  elif grep -qE "^\[FAIL\] $target " "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"
    pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^\[FAIL\]" "$out" | head -4 | sed 's/^/         实际红的是:/'
    fail=$((fail+1))
  fi
}

echo "== 安装器静态闸红检 =="

# M1 要管理员 —— 装到需要提权的地方,应用内更新就废了
mutate_and_expect M1 G1 "$NSI" \
  '
RequestExecutionLevel user' '
RequestExecutionLevel admin'

# M2 装进 Program Files
mutate_and_expect M2 G2 "$NSI" \
  'InstallDir "$LOCALAPPDATA\Programs\${APP}"' 'InstallDir "$PROGRAMFILES\${APP}"'

# M3 数据目录挪进安装根里面 —— 卸载整棵删的时候业主两年的档案跟着走。
#    ⚠️ 这条最初漏网:闸拿字符串比,看不出 `$INSTDIR\data` 在安装根里面。
#    已修(check-installer.py 的 resolve() 把 $INSTDIR 还原成实际路径)。
mutate_and_expect M3 G3 "$NSI" \
  '!define DATA_ROOT  "$LOCALAPPDATA\${APP}"' '!define DATA_ROOT  "$INSTDIR\data"'

# M4 默认卸载路径上加一条删数据
mutate_and_expect M4 G4 "$NSI" \
  '  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"' \
  '  RMDir /r "${DATA_ROOT}"
  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"'

# M5 "删我的资料"变成默认勾上
mutate_and_expect M5 G5 "$NSI" \
  'Section /o "un.连我的资料一起删掉' 'Section "un.连我的资料一起删掉'

# M6 递归删安装目录之前不认门了 —— NSIS 最出名的那次事故
mutate_and_expect M6 G6 "$NSI" \
  '  IfFileExists "$INSTDIR\${SENTINEL}" 0 not_ours
    RMDir /r "$INSTDIR"' \
  '  RMDir /r "$INSTDIR"'

# M7 往 HKLM 写 —— 要管理员,而且卸载后业主删不掉
mutate_and_expect M7 G7 "$NSI" \
  'WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"' \
  'WriteRegStr HKLM "Software\${APP}" "InstallDir" "$INSTDIR"'

# M8 卸载后开机自启还在 ⇒ 每次开机弹"找不到文件"
mutate_and_expect M8 G8 "$NSI" \
  '  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"' '  ; 自启项不删了'

# M9 卸载了但"应用和功能"里那条还在
mutate_and_expect M9 G9 "$NSI" \
  '  DeleteRegKey   HKCU "${UNINST_KEY}"' '  ; 卸载条目不删了'

# M10 WebView2 检测指向一个不存在的组件 ⇒ 老机器上窗口开不出来还只给英文栈
mutate_and_expect M10 G10 "$NSI" \
  '!define WV2_GUID   "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"' \
  '!define WV2_GUID   "{00000000-0000-0000-0000-000000000000}"'

# M11 安装器开始经手凭据 —— design 拍板它全程不碰
mutate_and_expect M11 G11 "$NSI" \
  '  WriteRegStr HKCU "Software\${APP}" "Version"    "${APPVER}"' \
  '  WriteRegStr HKCU "Software\${APP}" "apiKey"     "$0"'

# M12 ANSI 版 ⇒ 中文用户名/中文路径当场乱码
mutate_and_expect M12 G12 "$NSI" 'Unicode true' 'Unicode false'

# M13 快捷方式直指 python ⇒ 业主看到的是 Python 的名字和图标
mutate_and_expect M13 G13 "$NSI" \
  'CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP}.exe"' \
  'CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\python\pythonw.exe"'

# M14 开机自启变成默认勾上 —— 业主明说它该是个选项
mutate_and_expect M14 G14 "$NSI" \
  'Section /o "开机时自动启动"' 'Section "开机时自动启动"'

# M19 目录页的守卫被拆成空壳 —— 装进非空目录时没人拦,卸载时把业主的东西一起删
mutate_and_expect M19 G15 "$NSI" \
  '  FindFirst $0 $1 "$INSTDIR\*.*"' '  ; 不数了'

# M15 启动器变成会弹安装界面的东西
mutate_and_expect M15 L1 "$LAU" '
SilentInstall silent' '
SilentInstall normal'

# M16 启动器用 python.exe ⇒ 任务栏上挂一个黑窗口,业主会以为中毒了
mutate_and_expect M16 L4 "$LAU" \
  'Exec '\''"$EXEDIR\python\pythonw.exe"' 'Exec '\''"$EXEDIR\python\python.exe"'

# M17 启动器等着不退 ⇒ 一直挂在任务管理器里
mutate_and_expect M17 L5 "$LAU" \
  'Exec '\''"$EXEDIR\python\pythonw.exe"' 'ExecWait '\''"$EXEDIR\python\pythonw.exe"'

# M18 包被装坏时不吭声 ⇒ 业主双击没反应,没有任何线索
mutate_and_expect M18 L6 "$LAU" \
  '    MessageBox MB_ICONSTOP "${APP} 好像没装完整:找不到$\n$EXEDIR\python\pythonw.exe' \
  '    DetailPrint "no python$\n'

# M20 🔴 subkimi 抓到的真洞:用 NSIS 续行把删数据的目标藏到下一行。
#     闸原来按物理行切词 ⇒ 这条删除的目标整个看不见,G4 绿、G6 还会说"没有递归删"。
#     修法是拼行再分析(不是禁用续行 —— 文案里正大量用着)。
mutate_and_expect M20 G4 "$NSI" \
  '  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"' \
  '  RMDir /r \
    "${DATA_ROOT}"
  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"'

# M21 快捷方式改到"所有用户"上下文 ⇒ 每用户身份写不进也删不掉,卸载后永远留在开始菜单
mutate_and_expect M21 G16 "$NSI" \
  'Section "在桌面上放一个图标" SecDesktop
  SetShellVarContext current' \
  'Section "在桌面上放一个图标" SecDesktop
  SetShellVarContext all'

# M22 不生成卸载器 ⇒ 编译照样成功,卸载条目指向一个不存在的 exe
mutate_and_expect M22 G17 "$NSI" \
  '  WriteUninstaller "$INSTDIR\卸载.exe"' '  ; 不生成卸载器了'

restore
A1="$(sha256sum "$NSI" | cut -d' ' -f1)"; A2="$(sha256sum "$LAU" | cut -d' ' -f1)"
echo
if [ "$B1" != "$A1" ] || [ "$B2" != "$A2" ]; then
  echo "🔴 还原失败:.nsi 与开跑前不一致"
  exit 2
fi
echo "两份 .nsi 已原样还回(sha256 一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
