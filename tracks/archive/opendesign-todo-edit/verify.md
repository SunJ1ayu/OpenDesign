# Verify: opendesign-todo-edit

- Date: 2026-07-15
- Verdict: PASS

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(写路径 + 数据一致性触发 → 主+3)。

## Mechanical checks

- [x] build passes — `cd web && npm run build`(tsc -b + vite)零错;dist 重建。
- [x] tests pass — `python3 -m pytest tests/ -q` = 236 passed / 7 skipped;`node --test tests/*.mjs` = 4/4 OK。
- [x] no secrets / unsafe ops — 无秘密;唯一写口是受控针孔 `/api/changes/edit`(见下)。
- [x] deployment-target 校验 — 真起 ds_web v0.9.0,POST 编辑→GET changes/health 闭环:
      health 回显 0.9.0、编辑落地保 `【客厅】` 前缀、changes 带回 history+note、raw 文件独立
      `## 变更历史` 段正确、页脚 bump。运行态与磁盘一致。

## Review

- lane: full(主 agent + submimo + subsense + subglm)。oracle 先跑:pytest rc=0(panel 记录)。
- 主 agent 独立评审(读 employee 前落 findings,见 /root/aiwork/tasks/opendesign-todo-edit-my-review.md):
  - **Finding A(correctness,medium)—— 已修**:`_EDIT_PREFIX_RE` 状态钉死 4 词集,但 line_re 定位
    任意状态主行 → 对非标准状态行只改正文(不带 new_status)时 `pm=None` → `pm.group` 崩 → HTTP 500。
    修:状态类改 `[^\]]*`;回归测试 `test_e12_edit_text_nonstandard_status`。
  - **Finding B(data-consistency,low)—— 已修**:`_EDIT_PREFIX_RE` 空间子模式比 parse_change 松,
    畸形 `【 】` 后端/读侧拆分漂移。修:镜像 `【[^【】\s][^【】]{0,15}】`,写读逐字节一致。
- employee findings(独立,未看主 agent 评审):
  - **submimo → PASS**(逐条 file:line 核 7 不变量;无 BLOCK/NEEDS_MORE)。
  - **subsense-agent(DeepSeek)→ PASS**(7 类不变量表格 + file:line;确认 `_EDIT_PREFIX_RE` 空间类
    与 CHANGE_RE 逐字节一致=finding B 已修;非标准状态被接纳=finding A 已修)。
  - **subglm-agent(GLM)→ PASS**(安全 7 层 + BLOCK-1/2/3 + no-op + 并发 + 前端逐点核;无 BLOCK)。
- 主裁(逐条给基),对两条 non-blocking observation:
  - **[REJECT] Content-Length 信任**(subsense/submimo):`_edit_change` 闸 `0<n≤4096` 后 `rfile.read(n)`,
    与既有 `_open_folder`(ds_web.py:504-511)逐字节同 posture;本地服务;短 body → JSON 解析失败 → 400。
    非回归,一致于已接受模式 → 拒。
  - **[REJECT] 错误码入响应体**(bad_name/path_escape,subsense):不回显路径/名字;且服务本地限定
    (127.0.0.1 + Host 闸),`/api/projects` 本就对本地客户端公开全部项目名 → 错误码粒度不构成超出
    已公开信息的存在性 oracle → 拒。
  - 主 agent 自查 shared-blindspot(unanimous PASS 不降标):注入面(note/new_text 经 sanitize_field
    折行 + `- C{n} 备注:`/前缀捕获 → 无法伪造 `- [状态]` 账本行,核 test 通)、历史段跨 cnum 时序与
    parse_history 分桶隔离、前端乐观 tag/reload 边界 —— 均无遗漏。

## Accepted deviations

- 待办页数据源 `/api/todos` 不带 history/note → TodoPage「改过·看原文」是**本会话乐观留痕**
  (改正文后本地记旧值悬浮);持久历史在工作台变更列(/changes 端点带 history)。有意不扩
  /api/todos(collect 单一真相源,爆炸面大),保持 T6 最简。
- 前端 note 无法与现有 note diff(OpenItem 无 note 字段)→ 重复提交同一 note 会 re-write(后端替换
  同值 → footer bump)。噪声极小,非正确性问题。
- edit_change 未注册为 MCP 工具:edit 只走工作台针孔;agent 仍用 append/set_status(有意收窄写面)。
- 前端浏览器真机点测(driving the running dist in a browser)UNTESTED on target —— 后端 e2e + tsc/vite
  build + mjs 纯函数 oracle 已覆盖逻辑与协议;真机 UI 点测留待用户在 Windows 工作台验收。
