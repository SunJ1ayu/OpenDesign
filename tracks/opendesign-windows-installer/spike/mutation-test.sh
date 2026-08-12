#!/usr/bin/env bash
# 红检(变异测试)—— 证明 spike.py 这份判据咬得动。
#
# 规矩:变异的是**被测对象**(包的内容),不是判据本身;改判据让它变红只能证明它会打字。
# 每条变异都指定**靶子**:必须是那一条红,不是"随便红了就算过"
# (08-11 变异脚本三次把靶子指错,红在别处还自称通过)。
#
# 用法:mutation-test.sh <rig 目录>

set -u
RIG="${1:?用法: mutation-test.sh <rig 目录>}"
PY="$RIG/python/bin/python"
[ -x "$PY" ] || { echo "找不到 $PY"; exit 2; }

pass=0; fail=0

# 跑一遍 spike,判断靶子那一条是不是 FAIL 了
run_and_expect() {
  local id="$1" target="$2" out
  out="$RIG/mut-$id.txt"
  ( cd "$RIG" && timeout 900 ./python/bin/python spike.py ) > "$out" 2>&1
  if grep -qE "^\s+\[FAIL\] $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"
    pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 靶子 $target **没红**:这条变异下判据是瞎的"
    grep -E "^\s+\[FAIL\]" "$out" | head -5 | sed 's/^/         实际红的是:/'
    fail=$((fail+1))
  fi
}

echo "== 红检开始 =="

# W1 靶子 S4b:装机脚本失败必须被看见(rc 不许被吞)
echo "[W1] 把 enable_webui.py 弄成非 0 退出"
cp "$RIG/ds/bin/enable_webui.py" "$RIG/.bak-webui"
printf 'import sys\nsys.exit(1)\n' > "$RIG/ds/bin/enable_webui.py"
run_and_expect W1 "S4b"
cp "$RIG/.bak-webui" "$RIG/ds/bin/enable_webui.py"

# W2 靶子 S4e:config 里把 key 写死成字面量(= 占位符没被解析的等价形状)
echo "[W2] 模板里的 \${DS_LLM_KEY} 改成写死的假 key"
cp "$RIG/ds/config/nanobot.config.windows.jsonc" "$RIG/.bak-tpl"
sed -i 's/\${DS_LLM_KEY}/sk-hardcoded-wrong/' "$RIG/ds/config/nanobot.config.windows.jsonc"
run_and_expect W2 "S4e"
cp "$RIG/.bak-tpl" "$RIG/ds/config/nanobot.config.windows.jsonc"

# W3 靶子 S3:文档转换器转出来的东西不对(拿一个假 anydoc 顶掉真的)
echo "[W3] 用一个返回空字符串的假 anydoc 顶掉真的"
printf 'def to_markdown(p, *a, **k):\n    return ""\n' > "$RIG/anydoc.py"
run_and_expect W3 "S3"
rm -f "$RIG/anydoc.py" "$RIG/__pycache__/anydoc"*.pyc 2>/dev/null

# W4 靶子 S5-pre:别人占着端口时,不许把别人的应答当成我们的绿
echo "[W4] 先占住 18795,再跑"
"$PY" -c "
import socket,time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('127.0.0.1',18795)); s.listen(5)
time.sleep(600)
" &
SQUAT=$!
sleep 2
run_and_expect W4 "S5-pre"
kill $SQUAT 2>/dev/null; wait $SQUAT 2>/dev/null

# W5 靶子 S5b:工具服务连不上必须被看见
echo "[W5] 把 ds_mcp.py 弄成起不来"
cp "$RIG/ds/bin/ds_mcp.py" "$RIG/.bak-mcp"
printf 'import sys\nsys.exit(3)\n' > "$RIG/ds/bin/ds_mcp.py"
run_and_expect W5 "S5b"
cp "$RIG/.bak-mcp" "$RIG/ds/bin/ds_mcp.py"

# W6 靶子 S0a:用机器上装的 python 跑,必须当场识破
echo "[W6] 改用系统 python 跑(冒充'包内解释器')"
out="$RIG/mut-W6.txt"
( cd "$RIG" && timeout 300 /usr/bin/python3 spike.py ) > "$out" 2>&1
if grep -qE "^\s+\[FAIL\] S0a" "$out"; then
  echo "  [OK]   W6 -> 靶子 S0a 如期红了"; pass=$((pass+1))
else
  echo "  [BAD]  W6 -> 靶子 S0a **没红**:判据认不出自己在用谁的解释器"; fail=$((fail+1))
fi

rm -f "$RIG/.bak-webui" "$RIG/.bak-tpl" "$RIG/.bak-mcp"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
