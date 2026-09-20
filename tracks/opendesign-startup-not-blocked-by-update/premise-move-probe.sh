#!/usr/bin/env bash
# 「我只是多摆了一个前提,没有放松任何断言」—— 这句话的机器证明。
#
# 2026-09-20:本单把 test_ds_web_auto_update.py(上一单 opendesign-auto-update-countdown
# 的锁定考卷)里 21 个自动安装请求的**前提**改了:发请求之前先把"后台已备好的包"摆上。
# 这是业主 09-19 换规格的直接后果(自动安装装的是盘上那个包,不再是"这一刻查到的新版")。
#
# 改别人家的考卷是最容易放水的动作。所以这里问两件事,两件都得成立:
#   ①【没放松】把本单的实现**撤掉**、只留改过的考卷 ⇒ 旧实现必须**照样全绿**。
#      前提是多摆的,旧实现根本不读它 ⇒ 绿 = 我没有把任何一条断言改软。
#      要是这里红了,说明我动的不是前提,是断言本身。
#   ②【不恒绿】同一份旧实现下,本单新写的那一卷(ai1~ai6)必须**红**。
#      绿 = 新卷问不出本单在修的那件事。
set -uo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
git stash push --quiet -- bin/ds_web.py bin/ds_update_startup.py || exit 90
trap 'git stash pop --quiet' EXIT
echo "== 撤掉本单实现(bin/ds_web.py 与 bin/ds_update_startup.py 回到 HEAD)"
git diff --stat HEAD -- bin/ds_web.py bin/ds_update_startup.py | tail -1
echo
echo "== ① 旧实现 + 新前提:上一单那份锁定考卷必须照样全绿"
"$PY" -m unittest tests.test_ds_web_auto_update 2>&1 | tail -3
a=${PIPESTATUS[0]}
echo
echo "== ② 旧实现 + 本单新卷:必须红(否则新卷问不出东西)"
"$PY" -m unittest tests.test_ds_web_auto_install_local 2>&1 | tail -3
b=${PIPESTATUS[0]}
echo
if [ "$a" -eq 0 ] && [ "$b" -ne 0 ]; then
  echo "判定:✅ ①绿(没放松) + ②红(不恒绿)—— 前提搬移成立"; exit 0
fi
echo "判定:🔴 ①rc=$a(要 0) ②rc=$b(要非 0)—— 前提搬移不成立"; exit 1
