#!/usr/bin/env bash
# 红检 —— 证明 track opendesign-sidebar-history 的判据**咬得动实现**(照 tests/mutation-composer-zcode.sh 的做法)。
#
# 判据先行时红在「模块不存在」上;那种红只证明"没有就会响",不证明"写错了会响"。
# 每条变异只弄坏一处,并核对**红在该红的那一问上**(光看退出码,超时、夹具炸也是非 0 —— 那是假的咬住)。
# B 段 = 后台(ds_sessions / ds_web),F 段 = 前台纯逻辑(sidebarModel),E 段 = 界面(要重新构建再跑 e2e)。
# Python 判据前先删这两个模块的 .pyc:同长度替换 + 同一秒 mtime 会让 CPython 复用旧字节码(08-07 红检被它骗过)。
#
# 用法:tests/mutation-sidebar-history.sh [变异号...]    退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
WORK="$(mktemp -d)"
SRCS=(bin/ds_sessions.py bin/ds_web.py web/src/workspace/sidebarModel.ts web/src/workspace/Sidebar.tsx web/src/App.tsx web/src/app.css)
for s in "${SRCS[@]}"; do cp "$s" "$WORK/$(basename "$s").orig"; done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
rebuilt=0
cleanup() {
  restore
  rm -f bin/__pycache__/ds_sessions.*.pyc bin/__pycache__/ds_web.*.pyc
  if [ $rebuilt -eq 1 ]; then (cd web && npm run build >/dev/null 2>&1) && echo "(已按还原后的源码重新构建 web/dist)"; fi
  rm -rf "$WORK"; echo "(已还原源码)"
}
trap cleanup EXIT
pass=0; fail=0; only=("$@")

wanted() {
  [ ${#only[@]} -eq 0 ] && return 0
  for x in "${only[@]}"; do [ "$x" = "$1" ] && return 0; done
  return 1
}

# mutate <id> <文件> <老串> <新串> <判据命令> <该红在哪一问> <说明>
#   该红在哪一问:「s3」= node 单测名;「py:test_xxx」= unittest 用例;其余 = e2e 输出里要出现的串
mutate() {
  local id="$1" file="$2" old="$3" new="$4" oracle="$5" marker="$6" why="$7"
  wanted "$id" || return 0
  restore
  python3 - "$file" "$old" "$new" <<'PY' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
n = s.count(old)
if n != 1:
    sys.exit(f"变异锚点出现 {n} 次(必须恰好 1 次): {old!r}")
p.write_text(s.replace(old, new), encoding="utf-8")
PY
  [[ "$oracle" == *"npm run build"* ]] && rebuilt=1
  local out rc hit=1
  out="$(timeout 900 bash -c "$oracle" 2>&1)"; rc=$?
  if [[ "$marker" =~ ^s[0-9]+$ ]]; then
    grep -qE -- "^not ok [0-9]+ - ${marker} " <<<"$out" && hit=0
  elif [[ "$marker" == py:* ]]; then
    grep -qE -- "^(FAIL|ERROR): ${marker#py:} " <<<"$out" && hit=0
  else
    grep -qF -- "$marker" <<<"$out" && hit=0
  fi
  if [ $rc -ne 0 ] && [ $hit -eq 0 ]; then
    echo "  [咬住] $id —— $why"
    pass=$((pass+1))
  else
    echo "  [漏网] $id —— $why(rc=$rc,没见到「$marker」)"
    tail -15 <<<"$out" | sed 's/^/        /'
    fail=$((fail+1))
  fi
}

PY="rm -f bin/__pycache__/ds_sessions.*.pyc bin/__pycache__/ds_web.*.pyc; PYTHONDONTWRITEBYTECODE=1 /root/.venvs/design-studio/bin/python tests/test_sidebar_history_api.py"
UNIT="node --test tests/test_sidebar_history.mjs"
E2E="(cd web && npm run build >/dev/null 2>&1 || { echo 构建失败:变异没编译过; exit 99; }) && node tests/e2e/sidebar_history.e2e.mjs"

# ── B 后台:对话碰过哪些项目 ──
mutate B1 bin/ds_sessions.py \
  '                    add(a.get("name"))' '                    pass' \
  "$PY" "py:test_p1_derived_mapping" "只读过档案(read_project 的 name)不算碰过"
mutate B2 bin/ds_sessions.py \
  '                alias[old] = new' '                pass' \
  "$PY" "py:test_p1_derived_mapping" "改名前的对话不归到新名下(4c C2)"
mutate B3 bin/ds_sessions.py \
  '            if hit is None or hit[0] != sig:' '            if hit is None:' \
  "$PY" "py:test_p3_changed_file_is_reread" "对话文件变了还用旧缓存"
mutate B4 bin/ds_sessions.py \
  '                if not isinstance(name, str) or not name.startswith(_TOOL_PREFIX):' \
  '                if not isinstance(name, str) or not name.startswith("mcp_"):' \
  "$PY" "py:test_p1_derived_mapping" "别的 MCP 服务的工具也算"
# ── B 后台:置顶 / 改名 / 删除 ──
mutate B5 bin/ds_sessions.py \
  '    out = dict(state)' '    out = {}' \
  "$PY" "py:test_s1_pin_unpin_keeps_other_fields" "置顶把文件里别的字段丢了"
mutate B6 bin/ds_sessions.py \
  '    with ds_common.archive_lock(path):' '    if True:' \
  "$PY" "py:test_e3c_concurrent_pins_none_lost" "读 - 改 - 写不加锁,同时点的置顶会丢"
mutate B7 bin/ds_web.py \
  '        if 200 <= status < 300 and deleted:' '        if True:' \
  "$PY" "py:test_e6_delete_failure_keeps_state" "网关拒删(409)也清了置顶 / 改名"
mutate B7b bin/ds_web.py \
  '        if 200 <= status < 300 and deleted:' '        if 200 <= status < 300:' \
  "$PY" "py:test_e6b_delete_blocked_by_automation_keeps_state" "网关因定时任务拒删(200 + deleted:false)也清了置顶 / 改名"
mutate B8 bin/ds_web.py \
  '                ds_sessions.update_sidebar(self.server.ds_root, lambda st: ds_sessions.forget_session(st, key))' \
  '                pass' \
  "$PY" "py:test_e5_delete_cleans_pin_and_title" "删了对话,置顶 / 改名残留(4c C11)"
mutate B9 bin/ds_web.py \
  '            self._json(200, ds_sessions.load_sidebar(self.server.ds_root))' \
  '            self._json(200, ds_sessions._read_state(ds_sessions.sidebar_path(self.server.ds_root)))' \
  "$PY" "py:test_e2_sidebar_state_only_two_fields" "把整份状态文件回给前端"
mutate B10 bin/ds_web.py \
  '            if not isinstance(pinned, bool):' '            if pinned is None:' \
  "$PY" "py:test_e4_rejects_without_writing" "pinned 不是布尔也收"
mutate B11 bin/ds_sessions.py \
  '    return t[:TITLE_MAX] if t else None' '    return t if t else None' \
  "$PY" "py:test_s4_clean_title" "改名不截到 160"
mutate B12 bin/ds_web.py \
  '        """POST 置顶 / 改名(track opendesign-sidebar-history)。闸序同删除针孔:CT json → key 白名单 → 字段类型。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":' \
  '        """POST 置顶 / 改名(track opendesign-sidebar-history)。闸序同删除针孔:CT json → key 白名单 → 字段类型。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if False:' \
  "$PY" "py:test_e4_rejects_without_writing" "置顶 / 改名不查 Content-Type(CSRF 纵深)"
mutate B13 bin/ds_web.py \
  '            fn = lambda st: ds_sessions.patch_sidebar(st, key, title=title)  # noqa: E731' \
  '            fn = lambda st: ds_sessions.patch_sidebar(st, key, title=title[:5])  # noqa: E731' \
  "$PY" "py:test_e3b_many_long_titles_all_kept" "长名字存不全"

# ── F 前台纯逻辑 ──
mutate F1 web/src/workspace/sidebarModel.ts \
  '  if (t >= today) return "今天";' '  if (t >= now.getTime() - 86400000) return "今天";' \
  "$UNIT" "s1" "今天按 24 小时滚动算,不是按本机日期"
mutate F2 web/src/workspace/sidebarModel.ts \
  '  let rest = byRecent(sessions.filter((s) => !pin.has(s.key)));' '  let rest = byRecent(sessions);' \
  "$UNIT" "s2" "置顶的在下面重复出现(4c C10)"
mutate F3 web/src/workspace/sidebarModel.ts \
  '  return overrides[s.key] || s.title || s.preview || "(未命名对话)";' '  return s.title || s.preview || "(未命名对话)";' \
  "$UNIT" "s3" "改过的名字不显示"
mutate F4 web/src/workspace/sidebarModel.ts \
  '    if (`websocket:${chatId}` === sessionKey) add(project);' '    if (false) add(project);' \
  "$UNIT" "s4" "项目对话不算碰过它的项目"
mutate F5 web/src/workspace/sidebarModel.ts \
  '      if (hits.length === 1) add(hits[0]);' '' \
  "$UNIT" "s4" "助手只写名字(分组项目)对不上"
mutate F6 web/src/workspace/sidebarModel.ts \
  '  const add = (k: string | undefined) => { if (k && keys.has(k) && !out.includes(k)) out.push(k); };' \
  '  const add = (k: string | undefined) => { if (k && !out.includes(k)) out.push(k); };' \
  "$UNIT" "s4" "删掉的项目还挂着对话"
mutate F7 web/src/workspace/sidebarModel.ts \
  '    for (const p of ps) (byProject[p] ??= []).push(s);' '    (byProject[ps[0]] ??= []).push(s);' \
  "$UNIT" "s5" "碰过两个项目只在第一个下出现"
mutate F8 web/src/workspace/sidebarModel.ts \
  '    byProject[p] = [...list.filter(own), ...list.filter((s) => !own(s))];' '    byProject[p] = list;' \
  "$UNIT" "s5" "项目对话不排最前"
mutate F9 web/src/workspace/sidebarModel.ts \
  '    if (pin.has(s.key)) continue;' '' \
  "$UNIT" "s5" "置顶的在项目下重复"
mutate F10 web/src/workspace/sidebarModel.ts \
  '  return t ? t.slice(0, TITLE_MAX) : null;' '  return t.slice(0, TITLE_MAX);' \
  "$UNIT" "s6" "清空名字不当取消"
mutate F11 web/src/workspace/sidebarModel.ts \
  '  return projectKeys.length > 1 ? `${first} +${projectKeys.length - 1}` : first;' '  return first;' \
  "$UNIT" "s7" "碰过多个项目的小标不带 +N"

# ── E 界面(真 chromium) ──
# 变异要编译得过:把某个回调的唯一调用删掉会被 tsc 当「没用到的变量」拒掉(rc=99,第 1 遍 E13/E14 就是),改成仍引用、不调用
mutate E1 web/src/workspace/Sidebar.tsx \
  'const TIME_FIRST = 10;   // 按时间先显示几条' 'const TIME_FIRST = 1000;   // 按时间先显示几条' \
  "$E2E" "not ok - ① 按时间" "一下全摊开,没有「先显示一部分」"
mutate E2 web/src/workspace/Sidebar.tsx \
  '{unpinnedCount > timeShown && moreBtn(() => setTimeShown((n) => n + MORE_STEP))}' \
  '{unpinnedCount > timeShown && moreBtn(() => setTimeShown((n) => n))}' \
  "$E2E" "not ok - ① 按时间" "「显示更多」点了没用,翻不到最早的"
mutate E3 web/src/app.css \
  '.side-scroll { flex: 1; min-height: 0; overflow-x: hidden; overflow-y: auto; padding-bottom: 8px; }' \
  '.side-scroll { }' \
  "$E2E" "not ok - ① 按时间" "中间不滚动,翻开 30 条把设置 / 项目栏挤出去(4c C5)"
mutate E4 web/src/workspace/Sidebar.tsx \
  '                    onClick={() => { setMenuId(null); onPinSession(s, !pinned); }}>' \
  '                    onClick={() => { setMenuId(null); onPinSession(s, pinned); }}>' \
  "$E2E" "not ok - ② ⋯ 置顶" "点「置顶」发的是取消置顶"
mutate E5 web/src/App.tsx \
  '      setSidebarState(await pinChatSession(s.key, pinned));' '      await pinChatSession(s.key, pinned);' \
  "$E2E" "not ok - ② ⋯ 置顶" "置顶存上了,界面不换"
mutate E6 web/src/workspace/Sidebar.tsx \
  '    if (t !== null && t !== displayTitle(s, titleOverrides)) onRenameSession(s, t);' \
  '    if (t !== displayTitle(s, titleOverrides)) onRenameSession(s, t ?? "");' \
  "$E2E" "not ok - ② ⋯ 改名:清空回车" "清空回车发了改名(起好的名字会没)"
mutate E7 web/src/workspace/Sidebar.tsx \
  '              if (e.key === "Enter") { e.preventDefault(); finishRename(s, id, true, e.currentTarget.value); }' \
  '              if (e.key === "Enter") { e.preventDefault(); finishRename(s, id, false, e.currentTarget.value); }' \
  "$E2E" "not ok - ② ⋯ 改名 ⇒" "回车不存名字"
mutate E8 web/src/App.tsx \
  '      .then((st) => { if (!stale) setSidebarState(st); })' '      .then(() => {})' \
  "$E2E" "not ok - ② ⋯ 改名 ⇒" "重开不读置顶 / 改名"
mutate E9 web/src/workspace/Sidebar.tsx \
  '    const list = pv.byProject[p.key] ?? [];' '    const list = pv.other;' \
  "$E2E" "not ok - ③ 按项目" "项目下挂的不是它的对话"
mutate E10 web/src/workspace/Sidebar.tsx \
  '      {view === "project" && sessions !== null && pv.other.length > 0 && (' \
  '      {view === "project" && sessions !== null && pv.other.length > 9999 && (' \
  "$E2E" "not ok - ③ 按项目" "没有「其他对话」"
mutate E11 web/src/App.tsx \
  '    for (const s of sessions ?? []) out[s.key] = sessionProjects(s.key, derivedProjects, projThreads, projects);' \
  '    for (const s of sessions ?? []) out[s.key] = sessionProjects(s.key, {}, projThreads, projects);' \
  "$E2E" "not ok - ③ 按项目" "后台读出的「碰过的项目」没用上"
mutate E12 web/src/workspace/Sidebar.tsx \
  '    try { localStorage.setItem(SIDE_VIEW_STORAGE_KEY, v); } catch { /* 记不住就算了 */ }' '' \
  "$E2E" "not ok - ④ 切换记住" "切换不记住"
mutate E13 web/src/workspace/Sidebar.tsx \
  '                    onClick={() => { setMenuId(null); onDeleteSession(s); }}>' \
  '                    onClick={() => { setMenuId(null); void onDeleteSession; }}>' \
  "$E2E" "not ok - ② ⋯ 删除" "菜单里的「删除」不删"
mutate E14 web/src/workspace/Sidebar.tsx \
  '        <button className="hist-row" title={title} onClick={() => onOpenSession(s)}>' \
  '        <button className="hist-row" title={title} onClick={() => void onOpenSession}>' \
  "$E2E" "not ok - ④ 点一条对话" "点对话回不去"

echo "红检:咬住 $pass / 漏网 $fail"
[ $fail -eq 0 ]
