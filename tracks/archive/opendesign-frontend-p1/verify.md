# Verify: opendesign-frontend-p1

- Lane: **full 四审**(新写口两个 = 安全面,Tiered execution §4)
- 日期: 2026-07-19

## 收货三硬闸(执行腿 Sonnet 5,额度中断后主 agent 接管收口)
1. oracle byte-diff(对 c5dddec):tests/ 零 diff ✅
2. 主 agent 亲跑:24 新 oracle + 全量 py 473 + mjs 8 + tsc + npm build 全绿;
   dist 哈希与提交产物一致 ✅
3. diff 逐行亲读(安全面):posture 与既有针孔逐条等强 ✅

## e2e
tests/e2e/frontend_p1.e2e.mjs(真 chromium + 真 ds_web,无 gateway)12 断言
首跑 ALL PASS:就地编辑正文落盘+历史留痕 / 暂存2→跳1→旧案 superseded→确认→
落位+被跳文件还在箱 / bind 下拉→关联→workspace.json 写映射+既有映射保留。
修复轮复跑 ALL PASS。

## Panel(主审 review 先落盘于 /root/aiwork/tasks/opendesign-frontend-p1-review-my-review.md)
oracle 预跑 rc=0。四腿结论:
- submimo: PASS(0 finding)
- subdeepseek-agent: PASS(3 观察:approve web 层 superseded 预检不对称=存量拒;
  双读 TOCTOU=良性拒;畸形 plan 500=收)
- subglm-chat: PASS(3 LOW:下标错位=证伪,planPreview 1:1 保序 intake.ts:50-66,
  deepseek 独立证同;畸形 plan=收;_now 格式=证伪,两处同 isoformat(seconds))
- subkimi: PASS(1 MEDIUM + 3 LOW)

## 仲裁与修复轮(d4615ca 后追加)
收 4 条,全修全绿:
1. **subkimi M1(主审漏,panel 价值实锤)**:amend_plan 读-改-写不持锁+非原子写
   → 并发 apply 交错会把 applied_at 抹掉/双 amend 写坏 JSON。修=与 apply_plan
   同一把 .apply.lock 串行化 + tmp+os.replace 原子写(oracle a10)。
2. 畸形 plan KeyError→500(三腿独立标)→ 干净 bad_plan 400(oracle a9)。
3. subkimi L3:bind 缺 _valid_proj_key 预闸(同 create 先例)→ 补(oracle 钉 a..b 拒)。
4. subkimi L4 oracle 空档 → 补 amend Host/body 超限/applied→409、bind body 超限。
拒 3 条均附证伪依据(见上)。

## 结论:PASS
验收断点(用户 Windows):git pull → install.ps1 → start.ps1,设置弹层回显 **0.30.0**
(0.22–0.30 一批);验收看点=变更行 hover「编辑」、收件箱方案行「跳过」、
未关联项目文件区下拉「关联」。
