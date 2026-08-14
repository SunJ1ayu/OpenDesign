#!/usr/bin/env bash
# 组包后的结构检查 —— 本机(Linux)能验的那一半,别把结构性错误留给业主去发现。
# 验不了的那一半(embeddable Python 真跑不跑得动)正是探路包本身要回答的问题。
#
# 用法:check-package.sh <包目录> [--app]
#   (不给):考卷形态(S0/S1a/S1b)—— 包里要有且只有一张考卷,且 跑一下.bat 指向它
#   --app  :出货形态(S1c)—— 装到业主机器上的那棵树,不带考卷,要带外壳与图标

set -u
B="${1:?用法: check-package.sh <包目录> [--app]}"
APP_MODE=0
[ "${2:-}" = "--app" ] && APP_MODE=1
bad=0
ok()  { echo "  [PASS] $1"; }
no()  { echo "  [FAIL] $1"; bad=$((bad+1)); }

echo "== 包结构检查:$B =="

[ -f "$B/python/python.exe" ] && ok "包内 python.exe 在" || no "包内 python.exe 缺失"

# 装错平台的轮子是最容易犯又最难当场看出的错:Linux 的 .so 一个都不许有。
n_so=$(find "$B/python/Lib/site-packages" -name '*.so' 2>/dev/null | wc -l)
n_pyd=$(find "$B/python/Lib/site-packages" -name '*.pyd' 2>/dev/null | wc -l)
[ "$n_so" -eq 0 ] && ok "没有 Linux .so 泄漏(0 个)" || no "混进了 $n_so 个 Linux .so —— 装成了本机平台的轮子"
[ "$n_pyd" -gt 50 ] && ok "Windows .pyd 有 $n_pyd 个" || no "Windows .pyd 只有 $n_pyd 个,不像装全了"

# ._pth 是全包最脆的一环:不放开 site,site-packages 根本不进 sys.path。
P="$B/python/python312._pth"
if [ -f "$P" ]; then
  grep -q '^import site' "$P"            && ok "._pth 放开了 site"          || no "._pth 没放开 site ⇒ site-packages 不会进 sys.path"
  grep -q 'Lib\\site-packages' "$P"      && ok "._pth 列了 site-packages"   || no "._pth 没列 site-packages"
  # ._pth 会**忽略 PYTHONPATH**,而 ds 的模块之间是平级 import(ds_web 直接 import ds_common)
  # ⇒ ds/bin 必须写死进 ._pth,否则子进程起不来。
  grep -q '\.\.\\ds\\bin' "$P"           && ok "._pth 写死了 ds/bin(._pth 会忽略 PYTHONPATH)" || no "._pth 缺 ds/bin ⇒ ds_web/ds_mcp 会 import 不到同级模块"
  # pywin32 靠一个 .pth 文件把 win32\lib 挂上路径,而 embeddable + ._pth 下 .pth 会不会被
  # 处理我在 Linux 上验不了 ⇒ 写死进 ._pth,不赌。
  grep -q 'Lib\\site-packages\\win32\\lib' "$P" && ok "._pth 写死了 pywin32 的 win32\\lib" || no "._pth 缺 win32\\lib ⇒ import pywintypes 可能仍然失败"
else
  no "._pth 文件缺失"
fi

# 只在 Windows 上才需要的依赖,在 Linux 上解析时会被**静默丢掉**(pip --platform 只管
# 挑轮子,sys_platform 标记还是拿本机判的)。2026-08-12 真机第一跑就炸在这上面。
AUDIT="$(dirname "$0")/win-deps-audit.py"
if [ -f "$AUDIT" ]; then
  if python3 "$AUDIT" "$B/python/Lib/site-packages" > /tmp/win-deps-audit.out 2>&1; then
    ok "没有漏掉的 Windows 条件依赖($(grep -oP '带 Windows 条件的必需依赖 \K\d+' /tmp/win-deps-audit.out) 个全在)"
  else
    no "漏掉了只在 Windows 上才需要的依赖:"
    grep '缺!!' /tmp/win-deps-audit.out | sed 's/^/         /'
  fi
else
  no "找不到 win-deps-audit.py"
fi

for p in nanobot mcp anydoc pydantic_core lxml PIL cryptography; do
  [ -e "$B/python/Lib/site-packages/$p" ] && ok "关键包 $p 在" || no "关键包 $p 缺"
done
[ -f "$B/python/Lib/site-packages/anydoc/_anydoc.pyd" ] && ok "anydoc 的 Windows 原生件在" || no "anydoc 的 .pyd 缺"

NEED="ds/bin/ds_web.py ds/bin/ds_mcp.py ds/bin/enable_webui.py ds/bin/ds_merge_config.py
      ds/config/nanobot.config.windows.jsonc ds/web/dist/index.html ds/版本号.txt"
if [ "$APP_MODE" = 1 ]; then
  # 出货形态多要四样:外壳两件、配置就绪脚本、托盘图标。
  # 少任何一件业主都装得上、打不开 —— 而"装得上"看起来就像成功了。
  NEED="$NEED ds/bin/ds_shell.py ds/bin/ds_shell_core.py ds/bin/ds_provision.py ds/assets/图标.png"
else
  NEED="$NEED 跑一下.bat"
fi
for f in $NEED; do
  [ -f "$B/$f" ] && ok "$f 在" || no "$f 缺"
done

# 考卷与入口必须对得上。**不写死 spike.py 的名字**:三种形态(S0/S1a/S1b)各有各的考卷,
# 写死一张会让另外两种形态的包永远红。这里查的是更该查的那件事 ——
# 包里有且只有一张考卷,且 `跑一下.bat` 指向的正是它。
# 挡的是:入口指向一张**不在包里**的考卷(业主双击后一闪而过,什么都没有),
# 或者包里塞了两张、业主跑到了答非所问的那一张(而它照样会打印一份像样的收据)。
if [ "$APP_MODE" = 1 ]; then
  # 出货形态**一张考卷都不许有**:业主拿到的是产品,不是卷子。
  stray=$(cd "$B" && ls spike*.py 跑一下.bat 2>/dev/null || true)
  n=$(printf '%s\n' "$stray" | grep -c . || true)
  [ "$n" = 0 ] && ok "出货形态里没有混进考卷/考卷入口" \
                || no "出货形态里混进了考卷或它的入口:$(printf '%s' "$stray" | tr '\n' ' ')"
else
spikes=$(cd "$B" && ls spike*.py 2>/dev/null || true)
n=$(printf '%s\n' "$spikes" | grep -c . || true)
if [ "$n" = 1 ]; then
  ok "包里有且只有一张考卷($spikes)"
  if grep -qF "$spikes" "$B/跑一下.bat"; then
    ok "跑一下.bat 指向的就是它"
  else
    no "跑一下.bat 没指向 $spikes ⇒ 业主双击会跑空"
  fi
else
  no "包里的考卷有 $n 张(应为 1):$(printf '%s' "$spikes" | tr '\n' ' ')"
fi
fi

# 外壳形态(S1a/S1b)必须带上外壳自己那两个文件 —— 少了任何一个,业主那趟真机白跑。
if [ -f "$B/spike-shell.py" ] || [ -f "$B/spike-shell2.py" ] || [ "$APP_MODE" = 1 ]; then
  for f in ds/bin/ds_shell.py ds/bin/ds_shell_core.py; do
    [ -f "$B/$f" ] && ok "$f 在(外壳形态)" || no "$f 缺 —— 外壳形态的包必须带它"
  done
fi

# 这个包是要**公开发布**的(OpenDesign 是 public 仓)。ds/ 里每一个文件都必须是仓库里
# 本来就有的 —— 否则就是把机器上的本地文件(工作区配置、key、业主数据)顺手公开了出去。
# 立这条的由来:第一版包里就混进了 `config/workspace.json`(.gitignore 明确排除的
# 本地工作区配置),是发布前扫出来的。**别指望下次记得,交给机器查。**
REPO_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
leak=0
while IFS= read -r f; do
  rel="${f#$B/ds/}"
  [ "$rel" = "版本号.txt" ] && continue
  if ! ( cd "$REPO_DIR" && git ls-files --error-unmatch "$rel" >/dev/null 2>&1 ); then
    echo "         ↳ 非仓库文件:$rel"
    leak=$((leak+1))
  fi
done < <(find "$B/ds" -type f)
[ "$leak" -eq 0 ] && ok "ds/ 里没有仓库外的文件(不会把本地数据发出去)" \
                  || no "ds/ 里混进了 $leak 个仓库外的文件 —— 这个包要公开发布,不许带"

# 版本号是 S5d 的锚:包里带的必须等于仓库里 ds_web.py 的 VERSION,否则那条断言在问空气。
REPO_V=$(grep -oP '^VERSION = "\K[^"]+' "$(dirname "$0")/../../../bin/ds_web.py" 2>/dev/null)
PKG_V=$(cat "$B/ds/版本号.txt" 2>/dev/null | tr -d '[:space:]')
[ -n "$REPO_V" ] && [ "$REPO_V" = "$PKG_V" ] && ok "版本号锚一致($PKG_V)" || no "版本号锚对不上:仓库 '$REPO_V' vs 包内 '$PKG_V'"

# cmd.exe 读 LF 的 .bat 会出怪事
if [ "$APP_MODE" = 0 ]; then
  file -b "$B/跑一下.bat" | grep -q CRLF && ok ".bat 是 CRLF 换行" || no ".bat 不是 CRLF ⇒ cmd 可能读出怪东西"
fi

n_cache=$(find "$B" \( -name '__pycache__' -o -name '*.pyc' \) 2>/dev/null | wc -l)
[ "$n_cache" -eq 0 ] && ok "没有本机编译的字节码残留" || no "残留 $n_cache 个 __pycache__/.pyc(会造成缓存骗人那类怪问题)"

echo "== 结构检查结束:$bad 条不合格 =="
[ "$bad" -eq 0 ] || exit 1
