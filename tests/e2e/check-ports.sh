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

if [ "$#" -gt 0 ]; then
  ports=("$@")
else
  # 端口的**唯一来源**是各场景文件自己那行 `const PORT = N`,这里不抄第二份。
  mapfile -t ports < <(grep -hoP '^const PORT = \K[0-9]+' tests/e2e/*.e2e.mjs 2>/dev/null | sort -un)
fi

if [ "${#ports[@]}" -eq 0 ]; then
  echo "🔴 一个端口都没扫到 —— 是 e2e 改了写法(不再是 \`const PORT = N\`)还是路径错了?"
  echo "   这种时候必须红:预检扫不到东西,等于没有预检。"
  exit 1
fi

busy=0
for p in "${ports[@]}"; do
  line="$(ss -lptnH "sport = :$p" 2>/dev/null || true)"
  [ -z "$line" ] && continue
  pid="$(printf '%s' "$line" | grep -oP 'pid=\K[0-9]+' | head -1)"
  cmd="$(ps -o cmd= -p "${pid:-0}" 2>/dev/null | head -1)"
  started="$(ps -o lstart= -p "${pid:-0}" 2>/dev/null | head -1)"
  echo "🔴 端口 $p 被占着:pid=${pid:-?}  起于 ${started:-?}"
  echo "   $cmd"
  busy=$((busy + 1))
done

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
