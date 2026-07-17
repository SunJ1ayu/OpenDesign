# Verify: opendesign-intake

- Date: 2026-07-17
- Verdict: PASS(四腿 panel 仲裁完成;subkimi 补跑结果后补,见 Deviations)

## Mechanical checks

- [x] build passes(vite build + `tsc --noEmit` OK,dist 进仓)
- [x] tests pass:py test_ds_intake 23 / test_ds_web_intake 10 / test_ds_organize 22
      (MCP 面 5 工具契约)/ test_ds_merge_config 3(+exec 断言)/ 全量既有 py 套件
      回归绿(venv 含 mcp/nanobot);mjs 8 套件全绿(intake_ui 5);
      e2e 真 chromium intake 13/13 + cockpit 回归 ALL PASS(NUL 修复后复跑)
- [x] 突变红检 4/4:建议歧义乱猜 / stage 名字闸 / 针孔工作区闸 / 针孔键白名单
- [x] no secrets / unsafe ops(新写面=针孔④,审计见下)

## Review

- lane: full(文件移动=数据安全 + 新 POST 写针孔;首次四腿:MiMo/DeepSeek/GLM/Kimi)
- oracle 先跑后审:PANEL_ORACLE_CMD rc=0(panel 日志头有记录)
- 主审独立 review(先落盘再读 panel):/root/aiwork/tasks/opendesign-intake-review-my-review.md
- panel 日志:/root/aiwork/logs/panel-opendesign-intake-review-20260717-170302.*

### 主审自查(读 panel 前)

1. **[HIGH,存量,已修] nanobot 内置 exec 默认开 = `.approved` 人工闸可绕**
   (schema.py restrictToWorkspace=False 亲验;deploy-security §0 不变量被打穿)。
   修复=两模板+ds_merge_config 强制 `exec.enable=false` + 测试断言 + 文档 §0 补记
   + 本机 dev config 同步;网络面核实安全(web 工具 GET-only+SSRF 拦内网,
   exec 有内网 URL 守卫)——洞只在文件系统,关 exec 闭合。
2. **[LOW,已修] `_pending_plans` 对 root 缺失 plan 调 `realpath("")`=cwd** → 加守卫。
3. 针孔④ 安全链逐层核实(CT/键白名单/plan_id 格式/工作区 within/快照复验/锁/审计)。

### Panel findings 仲裁(逐条给依据)

- **subsense(DeepSeek agent 腿,PASS)**:
  - `_pending_plans` root 类型缺失(MEDIUM)→ **与主审 #2 独立相撞,已修**(交叉验证)。
  - inboxDirs 覆盖可指工作区外=列举面外泄(LOW)→ **收,已修**:`_find_inbox` 加
    realpath+within 闸 + test_08b(含 symlink 候选变体)。
  - approve/apply 并发分析=安全(informational)→ 与主审 #3 一致,记录。
  - InboxCard 网络瞬断整卡消失(informational)→ **接受**,伴随列降级哲学一致。
- **subglm(火山 chat 腿,PASS;agent 腿 CodingPlan 未订死亡,按既有路由切 chat)**:
  - `_intake_approve` 缺 root 守卫、与 `_pending_plans` 不对称(MEDIUM)→
    **收,真 finding(主审只修了列表侧漏了批准侧),已修** + test(坏 plan 批准 403)。
  - `_valid_taxonomy` 不拒 ../绝对路径(LOW)→ **收,已修**:`_safe_rel_dir`
    (含 Windows 盘符),坏配置加载期整体降级。
  - `ds_organize._PLAN_ID_RE` 私有件耦合(LOW)→ **收,已修**:公共 `is_valid_plan_id`。
  - InboxCard 不显示服务端 truncated(LOW)→ **收,已修**:超 500 提示行。
  - 已批准未执行 plan 出现在卡片+approve 非幂等风险(LOW)→ **拒**:核实
    `ds_organize.approve_plan`(:203)对已批准 plan 只重写 marker 返回 ok=幂等,
    already_applied 才拒;CLI 批准过的 plan 出现在卡片可被人点掉=合理完成路径。
- **submimo(MiMo,重试后 PASS;首轮 rc=124=上游超时)**:
  - 测试缺口:symlink stage/Host 闸/plan root 空值(MEDIUM)→ **收,已补**:
    test_08c/08d、test_approve_bad_host_rejected、test_approve_malformed_plan_root。
  - 前端无并发点击保护(LOW)→ **拒**:`disabled={busy !== null}` 已锁全卡按钮
    (InboxCard.tsx),后端锁+already_applied 409 双兜底。
  - 子串匹配极端误绑(LOW)→ 与主审 #7 同判:歧义留空+人工确认兜底,**接受不改**。
  - lexists/list 对 symlink 不对称(INFO)→ **收,已修**(stage_intake islink 拒,
    并入上面 symlink 修复)。
- **subkimi(K3 首战:900s 超时;1800s 重试交卷 PASS,8 findings=四腿最深)**:
  - 首轮残卷:**CompanionColumn.tsx 含 NUL 字节**(三家都没抓到;cockpit commit
    带入,git 视其为二进制)→ **收,已修**(NUL→空格,全仓扫描无其他,重建绿)。
  - 重试卷(审的是修复轮前的码,4 条与修复轮独立相撞=双向验证):
    symlink 认领缺口(MEDIUM,它还点破 test_08c docstring 只测了一半)/
    批准侧 root 守卫不对称 / Host 闸与坏 plan 测试缺口 / truncated 不展示
    → 均已在修复轮落地(它的批评帮忙补齐了 test_08d stage 半边)。
  - 新收 3 条:**category 参数非串类型 TypeError**(LOW→已修 isinstance 闸)/
    **前端"文件未动"在部分执行场景失实**(LOW→改为"详见对话或审计日志")/
    **AGENTS.md 两处与新流程打架**(LOW→已修:83 行批准口径改双通道、92 行
    "谁绑谁=杠杆"改成"两配置独立,机主自己加白名单,卡片闸是受控例外";
    organize SKILL.md 步骤 3 补例外指引;design.md pending 口径对齐)。
  - 收 1 条 nit:planPreview 根目录直落显示空串 → 占位"(工作区根)"+mjs 用例。
  - **拒 1 条**(finding 4 针孔面比名字宽):与 design/任务书口径一致
    ("root 在工作区根内"),预览+人在环,已在 Accepted deviations 记录——
    非缺陷,命名语义之争,`not_intake_plan` 错误码保留。
  - 工具观察:K3 effort=max + 只读守卫(管道全拒)= 900s 不够,1800s 充裕;
    panel 场景 KIMI_TIMEOUT 建议 1800(记入 subkimi 记忆,不阻本 track)。

### arbitrated verdict(主裁)

**PASS**(四腿全 PASS:submimo/subsense/subglm-chat/subkimi;主审 PASS)。
修复轮共落 12 处(exec 硬化/批准侧 root 守卫/inboxDirs within/taxonomy 路径闸/
公共 plan_id 校验/truncated 提示/symlink 双侧对称/NUL 清除/category 类型闸/
部分执行措辞/AGENTS.md 双处对齐/planPreview 占位),全部有测试或回归钉住;
被拒 findings(approve 幂等性误判/前端双击/针孔面命名)均给了代码级依据。
修复轮后全量复跑:py 23+10+22+3 绿、mjs 6 绿、tsc 绿、e2e 13/13 ALL PASS。

## Accepted deviations

- resolver eval:MiMo 上游白天两次超时,恢复后补跑中(3 条 intake 用例已进 CASES;
  结果后补,不阻验收——工具路由非本 track 正确性判据)。
- subkimi 1800s 重试尚在跑:其首轮已贡献 NUL finding;四腿中三腿有完整 verdict
  (submimo/subsense/subglm 全 PASS),重试结果仅作补充证据。
- subglm agent 腿死因=火山 CodingPlan 未订阅(账号 2129933582,上游 400),
  按既有路由规则切 chat 腿完成;非本 track 问题。
- suggest_project 子串匹配保守(纯数字段不参与):漏绑靠聊天补,误绑窗口≈0。
- InboxCard 拉取失败静默隐卡:与伴随列降级哲学一致。
