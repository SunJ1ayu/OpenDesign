#!/usr/bin/env bash
# e2e 端口预检 —— 开跑之前先问:我们要用的端口上,有没有别人?
#
# 🔴 **为什么有它**(2026-09-07,track opendesign-stage-timer-e2e-red):
# `stage_timer.e2e.mjs` 连红 5 天以上,被三个单子当成"既有红"传下去。
# 真相是一个 **8 月 30 日留下的遗孤 ds_web 进程**一直占着 8814:
#
#   1. 它的父进程死了,它自己活着(占着端口)
#   2. 那次 run 的 trap 把它的 HOME(隔离家目录)删了 ⇒ 它读不到假 key
#      ⇒ 判定"没配大模型 key" ⇒ 前端弹遮罩 ⇒ **后面每一次点击都被拦下**
#   3. 而每条 e2e 的等待循环只问「/api/health 有没有人应答」,
#      **不问应答的是不是自己刚起的那个** ⇒ 它高高兴兴地对着一个
#      八天前的旧服务跑完整场,红了 4 条断言
#
# 杀掉遗孤之后同一条测试 **4 秒通过**(此前 92 秒全是点击重试超时)。
#
# 所以这道预检问的是**结果**:端口干不干净。它不杀任何进程 ——
# 谁占着就把 PID 和命令行印出来,让人自己决定。**fail closed:占着就不许开跑。**
#
# 用法:tests/e2e/check-ports.sh          # 扫所有 e2e 声明的端口
#       tests/e2e/check-ports.sh 8814     # 只看某几个
# 退出码:0 = 干净   1 = 有人占着

set -u
cd "$(dirname "$0")/../.."

LIST_ONLY=0
[ "${1:-}" = "--list" ] && { LIST_ONLY=1; shift; }

if [ "$#" -gt 0 ]; then
  ports=("$@")
else
  # 端口的**唯一来源**是各场景文件自己那行 `const PORT = N`,这里不抄第二份。
  # 🔴 **派生端口也要算**(2026-09-07,两条评审腿各自独立命中):
  #    button_roles.e2e.mjs:97 用 `spawnWeb(planRoot, PORT + 1)` 另起一个 ds_web
  #    ⇒ 8825,原来完全不在扫描范围里;gallery_head_buttons 的 PORT+1 = 8820
  #    碰巧被别的场景声明覆盖了 —— **是巧合,不是机制**。
  mapfile -t ports < <(
    for f in tests/e2e/*.e2e.mjs; do
      [ -e "$f" ] || continue
      base="$(grep -m1 -oP '^const PORT = \K[0-9]+' "$f" 2>/dev/null)"
      [ -n "$base" ] || continue
      echo "$base"
      # 同一个文件里 `PORT + N` 起的第二个服务
      grep -oP 'PORT\s*\+\s*\K[0-9]+' "$f" 2>/dev/null | sort -u | while read -r off; do
        echo $((base + off))
      done
    done | sort -un
  )
fi

if [ "$LIST_ONLY" = 1 ]; then
  printf '%s\n' "${ports[@]}"
  exit 0
fi

# `SS_BIN` 这个接缝**是为了这道闸自己能被判**:不给接缝,"ss 用不了"这条路
# 在任何装了 iproute2 的机器上都跑不到 ⇒ 它就是一条死断言,而死断言正是本单在治的病。
SS_BIN="${SS_BIN:-ss}"
# 🔴 把正在用的 SS_BIN 印出来:这个接缝信任任何"成功退出"的二进制 ——
#    实测 `SS_BIN=/bin/true` + 真监听 ⇒ 这道闸说"干净"(评审腿指出,我复现)。
#    接缝是为了可判性,代价是它可被指向说谎者;至少让屏幕上看得见用的是谁。
[ "$SS_BIN" = "ss" ] || echo "⚠️  端口预检用的不是默认 ss,而是:$SS_BIN"


if [ "${#ports[@]}" -eq 0 ]; then
  echo "🔴 一个端口都没扫到 —— 是 e2e 改了写法(不再是 \`const PORT = N\`)还是路径错了?"
  echo "   这种时候必须红:预检扫不到东西,等于没有预检。"
  exit 1
fi

busy=0
ss_broken=0
for p in "${ports[@]}"; do
  if ! line="$("$SS_BIN" -lptnH "sport = :$p" 2>&1 >/dev/null)"; then
    # 🔴 报错原文要留着。原来 `2>/dev/null` 把它扔了,于是屏幕上只剩一句
    #    "查不动",而下面的 TIP 还在教人 `kill <pid>` —— 此时根本没有 pid。
    echo "🔴 $SS_BIN 查端口 $p 时用不了(没装 iproute2?坏了?)—— **查不动就不许说干净**。"
    [ -n "$line" ] && echo "   它自己说:$line"
    ss_broken=1
    busy=$((busy + 1)); continue
  fi
  line="$("$SS_BIN" -lptnH "sport = :$p" 2>/dev/null)"
  [ -z "$line" ] && continue
  pid="$(printf '%s' "$line" | grep -oP 'pid=\K[0-9]+' | head -1)"
  cmd="$(ps -o cmd= -p "${pid:-0}" 2>/dev/null | head -1)"
  started="$(ps -o lstart= -p "${pid:-0}" 2>/dev/null | head -1)"
  echo "🔴 端口 $p 被占着:pid=${pid:-?}  起于 ${started:-?}"
  echo "   $cmd"
  busy=$((busy + 1))
done

if [ "$busy" -gt 0 ] && [ "$ss_broken" = 1 ]; then
  echo
  echo "⇒ 上面是**查不动**,不是查到了占用者 —— 没有 pid 可 kill。先把 ss(iproute2)弄好。"
  exit 1
fi

if [ "$busy" -gt 0 ]; then
  cat <<'TIP'

⇒ 这些端口是 e2e 自己要用的。上面那些多半是**上一次跑完没收干净的遗孤**
  (父进程被砍、它自己活下来)。**不清掉就开跑,测试会对着旧服务跑完整场并给出
  看起来像产品坏了的红** —— 2026-09-07 就是这么烧掉五天的。

  确认那是遗孤之后:kill <pid>(**一个一个杀,别 pkill -f**,
  那条命令在这台机器上把自己杀掉过)。
TIP
  exit 1
fi

echo "✅ e2e 端口预检:${#ports[@]} 个端口都没人占"
