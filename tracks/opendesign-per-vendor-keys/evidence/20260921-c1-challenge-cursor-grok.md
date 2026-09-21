I'll start from the user goal and the current key/switch path in the snapshot, then challenge the proposed behavior against real failure cases.
Next I’ll read the credential, shell, and model-picker code so the failure cases are grounded in the real switch path.
The switch path hinges on env injection and whether the gateway must restart; I’ll read those next.
The owner’s real goal is **stop re-pasting keys when going back and forth**. “点一下就换” is the comparison-page line, not his words; he never said how long a switch may take. The rest follows from that.

## 1. Fully built, the goal still fails

**Switch looks done, the next answer is still the other vendor.**  
He has both keys. He opens the composer menu (`ChatPage.tsx` `pickModel` → `POST /api/llm/model`) and picks a DeepSeek model. The chip updates from `readModelsResponse`. nanobot’s `_refresh_provider_snapshot` (`nanobot/agent/loop.py`) loads the whole config; any missing `${VAR}` is a `ValueError` (`nanobot/config/loader.py` `_env_replace`) that is `logger.exception`’d and **the old provider is kept**. Menu and chip say DeepSeek; the reply is still MiMo. That is exactly the hard constraint: display must match who is actually answering.

This is easy to hit if the second provider is written into `~/.nanobot/config.json` before the gateway process has that env var: first save of the other vendor, he clicks the other vendor before `ds_shell_bridge_restart` / `Supervisor.restart` finishes; or `child_env` still injects only one key (`ds_shell.py` `build_env` + `ds_shell_core.service_envs`).

**He “switched”, then gets an auth failure that does not say “switch failed”.**  
Unset var kills load; **empty string does not**. Experiment 3: load succeeds, that provider’s key is `""`, failure is at call time. He sees DeepSeek on the chip, then an English 401. He thinks DeepSeek is broken, not that this process never received the key he saved.

**He is still waiting on a streaming MiMo reply.**  
Same as today’s intra-vendor switch: refresh is on the *next* inbound message (`loop.py` `_process_message` → `_refresh_provider_snapshot`). Chip already says DeepSeek. For a designer, “当前厂商必须与真正在回答的一致” is false for that whole turn.

**If the implementation restarts the gateway on every vendor click:** websocket drops; `ChatPage` hides the model chip unless `view.kind === "connected"`; after five reconnect failures the copy is “连接不上,gateway 可能没在跑” (`reconnect.ts` `BACKOFF_MS`, ~15s). Linux ready was ~2.3s; **owner Windows restart was never measured**; cold start was ~4 minutes; `gateway_service` `ready_timeout=300`. He asked to switch vendors, not to debug a dead gateway. If restart fails after `select_model` already wrote the preset, config/UI are DeepSeek and the still-running gateway is MiMo.

**Upgrade “不用重填” is one `apiBase` string.**  
`_current_provider` / `status()` match `providers.custom.apiBase` to `PROVIDERS` (`ds_credential.py`). Trailing slash already makes the picker show no vendor (composer-model-picker review). Then the old `key.txt` is not attributed; the menu does not list that vendor; he pastes again.

**A “just list both vendors’ models” implementation that still writes `provider: "custom"`.**  
`ModelPresetConfig` has no `apiBase` (`nanobot/config/schema.py`). Endpoint comes from the named provider. `select_model` today always sets `"provider": "custom"` and only allows the current vendor’s ids. Chip can say `deepseek-v4-flash` while HTTP still goes to MiMo’s `providers.custom`.

## 2. Premise that falsifies the whole no-restart plan

**Live AgentLoop, next user message, actually calls the other host with the other key** — not “`load_provider_snapshot` returns the right snapshot.”

Experiment 1 only asked the loader. Same-vendor model switch already ships on this contract; cross-vendor also changes `apiBase` and `apiKey`. If the HTTP client is cached, or `_refresh` no-ops (`_provider_snapshot_loader is None`, or sticky `_active_preset` when `default_selection_signature` is only `signature[:2]` = model + provider name), you cannot keep “click → next sentence is the other vendor” without a restart. Then you are on the restart-per-switch family, and the unknown is owner-machine restart time vs. reconnect UX.

**Minimal falsifier:** two local mock OpenAI servers (two ports, two keys). Start gateway with both env vars and two `providers.*` entries. Send one message (assert host A). Write `agents.defaults.modelPreset` to the other preset (no restart). Send again; assert host B and key B. Also run the missing-var case and confirm the UI does *not* take the success path (today `_refresh` keeps the old provider).

If that live switch is false, redo: two files, one `providers.custom`, swap `${DS_LLM_KEY}` + `apiBase`, restart, and do not mark the chip current until websocket is back.

## 3. Simpler family, and how to tell them apart

**Simpler:** keep one live provider. Two files (migrate `key.txt` by current `apiBase`). Menu pick of the other vendor = copy that file into the one env var, mutate `providers.custom.apiBase` like `save()` already does, `ds_shell_bridge_restart`. `ds-nanobot.ps1` / Linux stay single-`${VAR}`. No second named provider, no “missing var kills the whole config.”

**It sacrifices** “点一下、下一句就是那家、对话还在” — every vendor hop is a planned disconnect. That is acceptable only if owner Windows `Supervisor.restart` is a few seconds *and* reconnect copy is “正在切换供应商”, not “gateway 可能没在跑”.

**Discriminating experiment:** on a Windows box like his, time `restart_gateway` from lock frame to websocket ready (not first-install cold start). If it is ≥ the ~15s scary reconnect line, or he treats that wait as failure, in-process switch is required. If it is ~2–3s, the simple family is enough for “don’t paste again.”

---

**Direction:** Treat vendor switch as the same seam as today’s model switch: change `modelPreset` onto a **second named provider** that already has its own `${VAR}`; **restart only when a secret must enter the gateway process** (first save or rotate). Do not put extra `${VAR}` in the ship template (`config/nanobot.config.windows.jsonc`); `ds_merge_config.py` does not re-merge on update. Add `providers.od_deepseek` (or equivalent) only when that key exists. `build_env` / `child_env` inject **every stored vendor key** into the gateway leg only. Menu lists a vendor only if that var is in the running gateway, not merely because a file exists. `models_status` / `_current_provider` must follow the **current preset’s `provider` field**, not only `providers.custom.apiBase`. POST must refuse (400, chip unchanged) if that provider cannot be resolved live — never the success path that today’s swallowed `_refresh` would lie with.

**Core bet:** After both keys have been injected once, nanobot 0.2.2 will, on the next inbound message, build a new client from the other `providers.*` entry (`load_provider_snapshot` → `make_provider`). Key text still never hits config (`save()` already keeps `apiKey` as `${VAR}`).

**How it works:**  
- Disk: per-vendor files under `.openDesign/`; upgrade copies `key.txt` to the vendor matching current `apiBase`; leave `key.txt` so `ds-nanobot.ps1` still has one file.  
- Config: MiMo stays `providers.custom` + `${DS_LLM_KEY}` (Linux `${MIMO_TP_KEY}` via `env_var_name`). DeepSeek is a second named provider + its own `${VAR}`, presets point at that name — required because presets have no endpoint field.  
- First time he pastes the other key: existing key-card save + `ds_shell_bridge_restart` (same as today). Until restart completes, that vendor is **absent** from the composer menu.  
- After that: `select_model` may pick the other vendor’s ids, writes `modelPreset` only, no restart — same as `ds_web._llm_model_post` today.  
- git-pull / Linux: template unchanged; if they never save a second vendor, config still has one `${VAR}`.

**Best at:** The thing he actually does — bounce MiMo ↔ DeepSeek without hunting keys — on the installed shell path, without teaching him “后台/环境变量/重启”, and without using reconnect as a switch animation.

**Sacrifices:** First save of the second vendor still waits on restart (honest: that is injecting a secret, not switching). In-flight turn stays on the old vendor (already true for models). Two `${VAR}`s in a live config will kill `ds-nanobot.ps1` / `bin/ds-nanobot` if those launchers never set the second var — do not add the second provider unless that key was saved; do not “fix” those launchers beyond still being able to run single-vendor. `status()` `writable` / env-shadowing stays a single-var story (`_env_key`); per-vendor hints must not claim the gateway has a key it was not started with.

**Blind spots in the brief:** “点一下就换” was agent copy. Restart-vs-not is not a UI preference; it is whether env can change without a new process (`ds_web.ds_shell_bridge_restart` docstring). Experiment 1 is not a live call. Empty vs missing env vars behave differently. Identity is still “`custom.apiBase` string.” Listing a vendor from files while the process lacks the var produces the silent old-provider failure. Watchdog / reconnect assume unplanned death (`Supervisor.restart` comments), not a vendor menu. Mid-turn mismatch is already accepted for models and will look like a failed vendor switch.

**Smallest first step:** The live two-mock-server experiment above, plus the missing-var case wired to “POST must not return 200 / chip must not change”. If live switch is true, implement storage + inject-all-keys + menu gated on live env, and only then lift `select_model`’s current-vendor check. If false, stop and take the one-provider + restart family; do not ship a chip that can lie.
