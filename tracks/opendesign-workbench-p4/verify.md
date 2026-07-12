# Verify: opendesign-workbench-p4

- Date: 2026-07-12
- Verdict: **PASS**(主裁;panel full:submimo PASS / subglm-agent PASS / subsense 无信号)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## Mechanical checks

- [x] build passes(`npm run build` 零错;dist 重构建进仓,`git status` 干净=src/dist 一致)
- [x] tests pass(py 全套含新 oracle:T1 空间 4 条 red-check + set_model 4 条 +
      health.model 2 条 + /api/changes space 透传收紧;mjs:workbench_p4 8 条
      (突变红检过)+ chat 31 条回归;**oracle 在 panel 发车前已跑,rc=0 记录在
      panel-opendesign-p4.launch.log**)
- [x] no secrets / unsafe ops(set_model.py 只碰 agents.defaults.model 单字段,
      备份先行;无新 HTTP 写端点,只读铁律不破,主 agent 亲手 diff 复核)

## e2e(真 gateway + 真模型,ds-web 0.5.0)

8/8 全绿(两轮:首跑 6/8 抓到 2 真 bug 修复后复跑全绿):登录→默认 3a / 设置弹层回显
v0.5.0+AI 模型真值 / 待办页项目卡+玄关/客厅/未标注空间小节+⛑11 天超期标签+其余项目行 /
按时间平铺 4 行 / ⌘K 搜「岩板」命中+<mark> 高亮+文件 tab 置灰 / 回车直达 2a 目标行
hl-flash / 技能卡「记一下」→3a 预填 / 聊天发送→真模型回复(主链路零回归)。
截图 /root/aiwork/logs/odw-p4-shots/e2e-0{1..7}.png。
e2e 首跑抓到的 2 真 bug(都已修,commit ceae2d0):① SearchPanel 复位/加载 effect
共用依赖,索引到位清空已敲 query;② /api/changes space 是 P2 占位恒 None 未接 T1。

## Review

- lane: **full**(T1 碰核心账本行格式 = data-consistency 触发,design.md 冻结的决策)
- 主审(先于读任何 panel 输出):/root/aiwork/tasks/opendesign-p4-review-my-review.md,
  verdict PASS;红线 5 条亲手核(只读铁律/账本注入面/正则回溯/health 健壮/XSS 面),
  自抓 2 真 bug 已修(见上),取舍 D1-D5 记入下方 deviations。
- findings 仲裁(logs `/root/aiwork/logs/panel-opendesign-p4.*`):
  - **submimo(PASS,3+1 findings)**:
    - F-cache LOW「SearchPanel docs 缓存与注释不符:索引到 app 关才失效,会话内新记
      的变更搜不到」→ **收,已修**:关闭即 `setDocs(null)`,重开重拉;e2e ⑥b 断言
      关→开→再搜命中。真 finding,主审漏(盲点=只看了打开路径没看会话生命周期)。
    - F1 LOW「set_model 备份非原子,.bak 是变异后内容」→ **半拒**:核 set_model.py:41-53,
      `original` 在 parse 前整读、`.bak` 写的就是它,与改前逐字节一致——"post-mutation"
      说法证伪;写 config 中断可截断属实,但 .bak 有原文可回,本地 CLI 接受 → D7。
    - F2 LOW 键盘 effect 无依赖数组 → 与 subglm #3 同条,已是 D5(有意为之防闭包过期)。
    - F3 NEGLIGIBLE Sidebar popRef 死代码 → **收,已删**(声明+ref 挂点+useRef import 三处)。
    - 测试缺口 top1「/api/health model 非字符串/空串未测」→ **收**:test_13 五怪值
      (123/True/[]/None/"")oracle,突变红检过(退化 isinstance 守卫→FAIL 实证)。
  - **subglm-agent(PASS,3 LOW)**:
    - #1「旧行正文恰以短【】开头时解析语义变化,"text 一个字不动"措辞过强」→ **收**:
      test_09 补 2 条契约测试(legacy 剥前缀=新语义钉死;正文孤立】留在 text),注释收窄
      为"无【】前缀的旧行"。磁盘零改动不变,属展示语义澄清非回归。
    - #2「set_model "一字不碰"措辞盖不住全文件 JSON 重排」→ **收**:docstring 收窄
      (字段值不碰,空白归一)。语义契约本就由 test_01 锁字段值。
    - #3 键盘 effect 依赖数组 → 同 D5。
  - **subsense(NEEDS_MORE_INFO)**:chat 腿盲评——commit 已全部提交,`git diff` 为空,
    它看不到代码(已知复发问题,见 review-tooling 队列"diff 空自动 INCLUDE"折中)。
    无信号,不计入;full lane 实际 = 主审 + submimo + subglm 三方。
- arbitrated verdict (主裁): **PASS** —— 主审 PASS 前提下,panel 抓到主审漏的 1 真 finding
  (搜索索引会话内过期)已修+e2e 断言;其余为措辞/死代码/测试缺口,全部收敛。修复后
  全套 oracle 绿(py+mjs),e2e 真 gateway 复跑 **9/9**(原 8 条+重开搜索新断言)。

## Accepted deviations

- D1 超期但无未办结条目的项目在待办页仅底部一行提示(无卡可标;ds-todo/list_todos
  提醒链路仍覆盖)。
- D2 搜索「图片」回车=跳项目工作区(图墙未建);「文件/对话」tab 置灰(上游未建,
  proposal non-goal)。
- D3 技能卡不显示使用次数(无数据源,不造假数);技能列表为静态真实能力清单
  (不放 CAD 转 3D 未接假卡,design D5)。
- D4 set_model 不校验模型 id 有效性(nanobot 侧才知道;错 id 重启后报错,.bak 可回)。
- D5 SearchPanel 键盘监听 effect 每渲染重挂(无依赖数组)——正确性无虞,微开销接受。
- D6 「来源」字段本轮不做(meta 行留位,proposal non-goal)。
- D7 set_model 写 config 非原子(中断可截断);.bak 为改前原文可手工回滚,本地 CLI
  工具接受,不上 temp+rename(与 ds_tools 原子写议题合并另排)。
