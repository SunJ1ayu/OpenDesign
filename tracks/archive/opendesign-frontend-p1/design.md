# Design: opendesign-frontend-p1

## ① 变更正文就地编辑(纯前端)
- ChangesColumn 变更行(仅 cnum!==null)加编辑入口:点开行内 input,
  Enter 保存 / Esc 取消 → editChange({project, cnum, new_text}) → onEdited()
  重拉(服务端为真相源,不做乐观 tag——与 TodoPage 的乐观回显不同,这里
  列表本来就整列重拉)。
- 后端 edit_change 早支持 new_text(保格式+历史段留痕),零改动。

## ② 收件箱单条纠偏 = 跳过(新针孔⑧ /api/intake/amend)
契约(核心 ds_intake.amend_plan(plan_id, drop, allowed_roots, ds_root)):
- drop = 要剔除的 operations 下标列表:非空 list、全 int(bool 不算)、无重复、
  全在范围内,否则 {"error":"bad_drop"}。
- plan 校验:bad_plan_id / plan_not_found / already_applied /
  superseded_at 已存在 → {"error":"plan_superseded"}。
- 剩余行 >0:用旧 plan 的 src_rel/dst_rel 原样构造 operations →
  ds_organize.stage_plan(plan["root"], ops, allowed_roots)(存在性/冲突/
  overwrite 全套复验免费复用);stage 失败 → 原样回传错误,**旧 plan 不动**。
- stage 成功(或剩余 0 行=整案取消):旧 plan JSON 写入
  superseded_at + superseded_by(新 plan_id 或 None)。**不删文件=审计留痕**。
- 返回 {"ok":True, "plan_id": 新id|None, "count": 剩余数, "dropped": n}。
- 已知窗口(接受):stage 成功后 supersede 写盘若失败,新旧两 plan 同时
  pending;两者 src 重叠,先 apply 一个后另一个 src_missing 拒,无双移风险。

配套:
- ds_organize.approve_plan / apply_plan 读到 superseded_at → {"error":"plan_superseded"}
  (堵 CLI ds-approve 与 MCP apply_plan 批到已废案)。
- ds_web._pending_plans 过滤 superseded_at(与 applied_at 同款)。
- 针孔 posture 逐条同 _intake_approve:CT json → body≤OPEN_BODY_MAX → 键白名单
  {"plan_id","drop"} → plan_id 格式闸 → plan root 必须落工作区根内(403
  not_intake_plan)→ amend_plan(allowed_roots=[工作区根])。
  错误映射沿用 _INTAKE_ERR_STATUS + plan_superseded:409 / bad_drop:400 / empty_plan:400。
- InboxCard:plan 行尾「跳过」小按钮 → amendIntake(planId,[i]) → localEpoch++。
  跳掉最后一行=整案自然消失。busy 期间禁用。

## ③ 项目↔文件夹关联(新针孔⑨ /api/projects/bind)
- 针孔薄壳:CT json → 键白名单 {"project","folder"} → 双非空 str →
  ds_tools.bind_project(名字闸/已发现文件夹两级匹配/原子写全在核心,零新面)。
  错误映射 _BIND_ERR_STATUS:bad_name 400 / project_not_found·folder_not_found 404 /
  workspace_not_configured·folder_ambiguous 409(folder_not_found/ambiguous 时
  透传 folders 候选名单,前端可提示)。
- CompanionColumn 新 props:folders(App 传 projects.filter(unregistered).map(key))、
  onBound(App bump dataEpoch)。unmapped 分支:folders 非空 → select 下拉+
  「关联」按钮;为空 → 保留现聊天提示文案。下拉值=unregistered 行的 key
  (bind_project 精确 key 匹配优先,天然命中)。
- api.ts:amendIntake / bindProject,错误约定同 editChange(抛 error code)。

## 版本
ds_web VERSION → 0.30.0(注释注明 track)。

## Oracle(主 agent 亲写,执行腿 off-limits)
- tests/test_ds_intake.py::AmendPlanOracle(核心契约全套+stage 失败旧案不动)
- (ds_organize 侧 approve/apply 拒 superseded 由 AmendPlanOracle::test_a8 钉住,不另开文件)
- tests/test_ds_web_intake.py::TestIntakeAmendPinhole(posture+compose:
  暂存2→跳1→pending 只剩新案1行→确认→落位,被跳的还在收件箱)
- tests/test_ds_web_api.py::TestBindProjectPinhole(posture+成功写映射+错误码)
