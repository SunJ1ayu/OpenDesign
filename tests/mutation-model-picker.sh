#!/usr/bin/env bash
# 红检 —— 证明输入框模型按钮那三份判据咬得动(track opendesign-composer-model-picker)。
#
#   段 A 后端  tests.test_ds_llm_model(lm1~lm8)  变异 bin/ds_credential.py、bin/ds_web.py
#   段 B 前端  tests/test_model_picker.mjs(mp1~mp6) 变异 web/src/chat/modelPicker.ts
#   段 C e2e   tests/e2e/model_picker.e2e.mjs     变异 web/src/chat/ChatPage.tsx、web/src/app.css
#
# 规矩同 tests/mutation-ds-update-apply.sh:每条指定靶子(**必须是它自己红**,红在别处不算),
# 跑完原样还回去并核哈希。
#
# 🔴 lm7(跨站 POST ⇒ 403)在实现之前就是绿的:跨站检查在 do_POST 入口,新接口天然被它盖住。
#    所以 lm7 "红过"这件事只能由这里的 a7 证明 —— 拿掉入口检查,它得红。
# 🔴 段 C 要重建 web/dist(e2e 跑的是产物不是源码)。开跑前整份备份 dist,收尾整份还原并核哈希;
#    还原不上 ⇒ 退出码 9,工作树留给人收拾。
# 🔴 c2 是这单最要紧的假绿路线:按钮换了字、后端根本没写。⑩ 会照绿,只有 ⑧(读盘上配置)咬得住。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

FILES=(bin/ds_credential.py bin/ds_web.py web/src/chat/modelPicker.ts web/src/chat/ChatPage.tsx web/src/app.css)
WORK="$(mktemp -d)"
dist_hash() { (find web/dist -type f -print0 | sort -z | xargs -0 sha256sum) | sha256sum | cut -d' ' -f1; }
BEFORE="$(sha256sum "${FILES[@]}")"
BEFORE_DIST="$(dist_hash)"
for f in "${FILES[@]}"; do mkdir -p "$WORK/orig/$(dirname "$f")"; cp -p "$f" "$WORK/orig/$f"; done
cp -a web/dist "$WORK/dist"
restore_src() {
  for f in "${FILES[@]}"; do cp -p "$WORK/orig/$f" "$f"; done
  find bin tests -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
DIST_TOUCHED=0
restore_all() {
  restore_src
  if [ "$DIST_TOUCHED" = 1 ]; then rm -rf web/dist && cp -a "$WORK/dist" web/dist; fi
}
trap 'restore_all; rm -rf "$WORK"' EXIT

bites=0; escapes=0

# apply <文件> <old> <new>:锚点必须恰好出现一次
apply() {
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
}

# verdict <编号> <靶子> <输出文件> <命中靶子的 grep -E 前缀> <全绿标记正则>
verdict() {
  local id="$1" target="$2" out="$3" redpat="$4" greenpat="$5"
  if grep -F -- "$target" "$out" | grep -qE "$redpat"; then
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif grep -qE "$greenpat" "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target"
    grep -E "$redpat" "$out" | head -3 | sed 's/^/      实际红的:/'
    escapes=$((escapes+1))
  fi
}

mut_py() {   # mut_py <编号> <靶子测试名> <文件> <old> <new>
  local id="$1" target="$2"; restore_src
  apply "$3" "$4" "$5" || { echo "  [BAD]  $id 变异没打上去"; escapes=$((escapes+1)); return; }
  local out="$WORK/mut-$id.txt"
  timeout 300 "$PY" -m unittest tests.test_ds_llm_model > "$out" 2>&1
  verdict "$id" "$target" "$out" '^(FAIL|ERROR): ' '^OK'
}

mut_node() { # mut_node <编号> <靶子前缀> <old> <new>
  local id="$1" target="$2"; restore_src
  apply web/src/chat/modelPicker.ts "$3" "$4" || { echo "  [BAD]  $id 变异没打上去"; escapes=$((escapes+1)); return; }
  local out="$WORK/mut-$id.txt"
  node --test tests/test_model_picker.mjs > "$out" 2>&1
  verdict "$id" "$target" "$out" '^not ok ' '^# fail 0$'
}

mut_e2e() {  # mut_e2e <编号> <靶子(断言标签开头)> <文件> <old> <new>
  local id="$1" target="$2"; restore_src
  apply "$3" "$4" "$5" || { echo "  [BAD]  $id 变异没打上去"; escapes=$((escapes+1)); return; }
  local out="$WORK/mut-$id.txt"
  DIST_TOUCHED=1
  # 只跑 vite(不跑 tsc):有的变异故意越过类型收窄,红检问的是运行时行为
  if ! (cd web && timeout 180 npx vite build > "$WORK/build-$id.txt" 2>&1); then
    echo "  [BAD]  $id build 没过 ⇒ 这条红检无效"; tail -3 "$WORK/build-$id.txt"; escapes=$((escapes+1)); return
  fi
  timeout 240 node tests/e2e/model_picker.e2e.mjs > "$out" 2>&1
  verdict "$id" "$target" "$out" '^  FAIL - ' '^ALL PASS'
}

echo "== 段 A 后端 lm =="
mut_py a1 test_lm4_ids_outside_the_current_catalog_are_refused bin/ds_credential.py \
  '    if model not in p["models"]:' '    if False:'
mut_py a2 test_lm3_nanobot_itself_reads_the_new_model bin/ds_credential.py \
  '.setdefault("defaults", {})["modelPreset"] = model' '.setdefault("defaults", {})["model"] = model'
# a3 照配置里的 model_presets 列(不按厂商目录)⇒ 换到 DeepSeek 后 MiMo 残留被列成能用
mut_py a3 test_lm5_deepseek_catalog_and_switching_to_pro bin/ds_credential.py \
  'models=[{"id": m, "label": m} for m in p["models"]])' \
  'models=[{"id": m, "label": m} for m in (cfg.get("model_presets") or {})])'
mut_py a4 test_lm8_mimo_models_come_from_the_template bin/ds_credential.py \
  '"models": _template_models()}' '"models": ["mimo-v2.5", "mimo-v2.5-pro"]}'
mut_py a5 test_lm5_deepseek_catalog_and_switching_to_pro bin/ds_credential.py \
  '    if model not in presets:' '    if False:'
# a6 配置读不出来时替业主建一份
# (锚点带上下一行:同一句 raise 在 save() 里还有一份,只取 select_model 这一份 —— 首跑因不唯一没打上去)
mut_py a6 test_lm6_missing_broken_or_unknown_config bin/ds_credential.py \
  '        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None
    if not isinstance(cfg, dict):' \
  '        cfg = {"providers": {"custom": {"apiBase": PROVIDERS["mimo"]["apiBase"]}}}
    if not isinstance(cfg, dict):'
# (锚点带上 do_POST 的 Host 检查那三行:do_GET 里也有一处一模一样的跨站检查 —— 首跑因不唯一没打上去)
mut_py a7 test_lm7_cross_site_post_is_refused bin/ds_web.py \
  '        if not self._host_ok():  # H2:针孔与 405 之前先验 Host(同 do_GET)
            self._json(403, {"error": "bad host"})
            return
        # track opendesign-key-onboarding:前端不再手输口令之后补的纵深。
        # 它挡"能被跨站触发的带副作用请求";浏览器同源策略与 _host_ok 各守另一面。
        if not self._same_site_ok():
            self._json(403, {"error": "cross-site"})' \
  '        if not self._host_ok():  # H2:针孔与 405 之前先验 Host(同 do_GET)
            self._json(403, {"error": "bad host"})
            return
        # track opendesign-key-onboarding:前端不再手输口令之后补的纵深。
        # 它挡"能被跨站触发的带副作用请求";浏览器同源策略与 _host_ok 各守另一面。
        if False:
            self._json(403, {"error": "cross-site"})'
# a8 current 不走 preset 优先规则 ⇒ 换完回包还报旧模型
mut_py a8 test_lm2_post_changes_only_the_active_preset bin/ds_credential.py \
  'current=ds_model.resolve_model(cfg),' 'current=cfg["agents"]["defaults"].get("model"),'

echo "== 段 B 前端纯逻辑 mp =="
mut_node b1 "mp1 " 'active: m.id === status.current }' 'active: false }'
mut_node b2 "mp3 " 'if (!status || status.models.length === 0) return [tail];' 'if (!status) return [tail];'
mut_node b3 "mp4 " 'active: m.id === status.current }' 'active: m.id === status.current || m === status.models[0] }'
mut_node b4 "mp5 " 'return status?.current || gatewayModel || "选择模型";' 'return gatewayModel || status?.current || "选择模型";'
mut_node b5 "mp6 " 'if (status !== 200 || !body || typeof body !== "object") return null;' 'if (!body || typeof body !== "object") return null;'
mut_node b6 "mp2 " '    { kind: "sep" },
    tail,' '    tail,'

echo "== 段 C e2e(每条重建 dist)=="
mut_e2e c1 "⑭" web/src/chat/ChatPage.tsx \
  '{view.kind === "connected" && (
            <div className="model-pick">' \
  '{(view.kind === "connected" || view.kind === "reconnecting") && (
            <div className="model-pick">'
mut_e2e c2 "⑧" web/src/chat/ChatPage.tsx \
  '                          else void pickModel(it.id);' \
  '                          else { setModels(models && { ...models, current: it.id }); setModelMenuOpen(false); }'
mut_e2e c3 "⑫" web/src/chat/ChatPage.tsx \
  '                          onOpenLlmKey?.();' '                          void 0;'
mut_e2e c4 "③" web/src/chat/ChatPage.tsx \
  '      {(variant !== "home" || transcript.messages.length > 0) && inputCard}' \
  '      <div className="chat-meta">已连接</div>
      {(variant !== "home" || transcript.messages.length > 0) && inputCard}'
mut_e2e c5 "⑥" web/src/app.css \
  '  bottom: 100%;
  right: 0;
  margin-bottom: 6px;' \
  '  top: 100%;
  right: 0;
  margin-bottom: 6px;'
# c6 「退出登录」换个地方留着(挂在已连接那条渲染路径上,e2e 走得到)
mut_e2e c6 "④" web/src/chat/ChatPage.tsx \
  '                <span className="caret">▴</span>' \
  '                <span className="caret">▴</span>
                <span className="item">退出登录</span>'

echo "== 咬住 $bites / 漏网 $escapes =="

restore_all; DIST_TOUCHED=0
AFTER="$(sha256sum "${FILES[@]}")"
if [ "$AFTER" != "$BEFORE" ] || [ "$(dist_hash)" != "$BEFORE_DIST" ]; then
  echo "🔴 恢复失败:被测文件或 web/dist 与开跑前对不上 —— 工作树需要人来收拾"
  exit 9
fi
echo "还原核对:5 个被测文件 + web/dist 与开跑前逐字节一致"
[ "$escapes" -eq 0 ]
