# Verify: opendesign-workbench-p2

- Date: 2026-07-11
- Verdict: **PASS**(panel full lane 四方一致 + 真 gateway e2e 8/8)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## Mechanical checks

- [x] build passes — `npm run build` 重构建后 git status 干净(dist 与 src 一致,
      哈希 index-9n5CIo5n.js / index-DMlGSn4l.css)
- [x] tests pass — Python 10 文件 123 用例全绿(test_ds_web_api 22 条,含硬化 2 条)
      + mjs 31/31(chat 逻辑层零改动的机械证明)
- [x] no secrets / unsafe ops — ds_web 保持只读(非 GET 全 405);refs 静态服务
      三闸(字符集 \Z / realpath within / 图片扩展白名单),主 agent 亲手突变
      验红:去 Gate B → traversal+symlink 两条红;去 _projects 闸 → symlink 用例红

## 验收红线(tasks.md 5 条,主 agent 逐条查)

1. chat 逻辑层(connection/transcript/markdown)diff 为空 ✅
2. 既有测试只增不改(仅新增 test_ds_web_api.py)✅
3. ds_web 无非 GET 路由、无写路径(open 全读模式)✅
4. 三闸齐全、oracle 各自验红过 ✅
5. dist 重构建后与 src 一致 ✅

## e2e(真 gateway + 真 MiMo,新四列 IA)

8/8:四列外壳+fixture 真数据 / 参考图静态路由真加载(naturalWidth>0)/
登录→ws 就绪 / 发送→busy 锁 / 流式上屏 / turn_end 解锁 / Enter 二轮 /
「✓ 标记完成」→聊天预填。截图 /root/aiwork/logs/odw-p2-shots/e2e-0{1,2,3}.png。
(首跑 7/8:第 8 项系测试竞态——点击后同步读值早于 React effect;最小复现证明
产品无恙,断言改 waitForFunction 后复跑 8/8。)

## Review

- lane: **full**(main + submimo + subsense + subglm-agent;
  日志 /root/aiwork/logs/panel-odw-p2.*.log,oracle 先跑 rc=0)
- 主审(先于读任何 employee 输出,/root/aiwork/tasks/opendesign-workbench-p2-my-review.md):
  PASS;L1 regex $→\Z(hardening)、L2 relTime 时区(显示级)、L3 prefill 覆盖
  draft(设计如此)
- findings 仲裁(每条有据):
  - submimo PASS,0 findings(自行实跑 collect 四状态过滤验证,与主审一致)
  - subsense PASS + 1 LOW:_projects listdir 直读,projects/ 内指向外部的
    symlink .md 泄露外部文件标题/阶段字段 → **验真收下**(核 ds_web.py 原
    188-193 行,确与 _project_file 闸不一致),已修(realpath+within 同一把闸
    + oracle 突变验红),commit 1e8bbf7
  - subglm-agent PASS + 3 观察:①parse_ref_line 与 find_refs 的 head 解析是
    copy-paste 非共用 helper → 验真,记 accepted deviation(重构碰稳定代码
    收益低);②onConnected 不在 ws effect deps → **拒**(函数式更新,行为
    正确,核 ChatPage.tsx);③/api/health 回显 ds_root → 存量(main 已有,
    D2 运维面需要),出范围不改判
- arbitrated verdict (主裁): **PASS**——主审 L1 与 subsense LOW 已修入
  1e8bbf7;其余全部为接受偏差或证伪

## Accepted deviations

- 变更行无「空间/来源」字段:读侧宽容恒 null,前端只渲染存在字段;写侧 schema
  扩展另 track(design.md 决策)
- 文件区空态占位:D 盘目录约定未定,等首装真实反馈(proposal non-goal)
- 「效果」分段无数据源(refs-index 只索引参考图),空态文案
- 切页(待办/日历/技能)卸载 ChatColumn = 对话不保留:P1 已知问题同源,用户
  明确暂缓,proposal non-goal,非本 track 回归
- parse_ref_line/find_refs head 解析两处逐字一致但未共用 helper(GLM 观察①)
- test_file_trailing_newline_404 是行为锁非单闸验红($ 旧行为下 Gate C 的
  splitext 也兜得住,\Z 属纵深防御)——如实记录,不冒充验红
- 深色模式:定稿仅浅色,设置里标「即将支持」

## 部署目标(deployment-target rule)

本 verify 全部在开发机(Linux)完成;**用户 Windows 真机 `git pull` + 刷新
浏览器后,以浏览器里看到四列工作区为准才算部署完成**(磁盘有 dist ≠ 已部署)。
bin/ 热加载但 ds_web.py 是常驻进程——**pull 后需重启 ds-web/gateway**。
