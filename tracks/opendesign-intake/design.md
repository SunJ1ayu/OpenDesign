# Design: opendesign-intake

- Change: opendesign-intake
- Status: final(07-17 用户拍板 D1=工作台卡片按钮 / D2=聊天驱动,均选推荐项)

> Panel 判定:不跑 panel-explore。这不是开放架构分叉——积累的先例把方向钉死了:
> 归类引擎=读配置表的确定性代码(07-09 拍板)、v1 只动无引用文件(07-09)、
> taxonomy v1.0=默认模板(07-12 定稿)、approve 硬闸=人工专属/MCP 无此工具(07-02)、
> ds_web 受控 POST 针孔 posture(open-folder/session-delete/edit-change 三先例)。
> 剩余自由度只有"确认面放哪/谁驱动流程"两个产品决策,呈给用户,不值一个 panel。

## Approach

聊天驱动 + 面板确认,四段流水线,全部落在既有安全轨道上:

1. **类目规则表 = taxonomy v1.0 的机读版**。`config/taxonomy.default.json` 进仓
   (类目 id/显示名/项目内目标夹/extensions/auto|suggest-only 标志),用户侧可放
   `config/taxonomy.json` 覆盖(workspace.json 同模式)。CAD/SU/MAX 等被引用类目
   标 suggest-only——引擎永不自动动它们(v1 铁律的机读化)。
2. **`bin/ds_intake.py` 确定性核心 + MCP 工具(挂 design-studio-organize server)**:
   - `list_inbox()`:workspace root 下找收件箱夹(候选名 00-收件箱/00收件箱/收件箱,
     projectsDir 容错同模式),列文件 + 规则表建议类目 + 建议项目(文件名 token 对
     已知项目唯一命中才建议,歧义=留空让 agent 问,不猜)。
   - `stage_intake(assignments)`:「文件→项目+类目」列表 → 构造 operations →
     直调 `ds_organize.stage_plan`(校验/冲突检查/快照全复用)→ 返回 plan_id。
   - 不新增 approve/apply 工具;apply 复用既有 MCP `apply_plan`(仍被 .approved
     硬闸挡着,模型自己批不了)。
3. **ds_web 两个端点**:
   - GET `/api/intake`(只读):收件箱清单+建议 + pending plans(读 organize/plans/
     未 approved 未 applied 的)→ 工作台卡片数据源。
   - POST 针孔④ `/api/intake/approve` `{plan_id}`(精确匹配;CT json + 键白名单 +
     plan_id 格式闸 + body 上限,posture 逐条同 edit-change):浏览器里人点
     「确认执行」= 人工确认本体 → `approve_plan` + `apply_plan` 一气呵成,
     apply 的整体快照复验兜 TOCTOU,audit 照记。
4. **前端收件箱卡片**(伴随列,cockpit 系列的第五块):收件箱文件数、待确认 plan 的
   src→dst 预览列表(像 diff)、「确认执行」按钮;dataEpoch 刷新门与 cockpit 同机制。
   v1 卡片**只展示+确认**,不做下拉改派(改派走聊天:「把那两张图放到万科城参考图」
   → agent 重新 stage)。

用户动线:丢文件进收件箱 → 聊天说"整理收件箱"(或 agent 会话开头主动报)→
agent 报建议并 stage → 工作台卡片亮出预览 → 点确认 → 文件归位,卡片清空。

## Decisions(07-17 用户拍板,均选推荐项)

- **D1 确认面 = 工作台卡片按钮** + 第 4 个受控 POST 针孔(先例齐全);
  拒了 ds-approve 命令行(Windows 无 UX)与 MCP approve 工具(拆硬闸)。
- **D2 v1 驱动方式 = 聊天驱动**(写面最小);卡片内下拉改派留 v2 按真实反馈定。

## Key trade-offs / risks

- **DS_ORGANIZE_ROOTS 必须含工作区根**才能整理收件箱(Track B 的
  root⟂DS_ORGANIZE_ROOTS 不变量保持:两份配置独立,部署文档写清"整理收件箱需把
  工作区根加进白名单",不隐式打通)。
- approve+apply 一键 vs 两步:选一键(按钮语义=确认执行);风险=点击后无反悔窗口,
  但 plan 预览就在按钮上方,且 v1 只动无引用文件、审计可查。
- 收件箱里的**目录**(用户丢整个文件夹):v1 整夹建议为单个 op(move 目录),
  不递归拆散——与"整夹移动才安全"铁律一致。
- 文件名冲突(目标已存在):stage_plan 既有 would_overwrite 拒绝 → agent 建议
  改名后重 stage(不做自动改名,v1)。

## Alternatives considered

- panel-explore:见顶部判定,自由度不足以养活一个 panel。
- UI 驱动一条龙(前端直接 stage+approve):写面大增、绕过 agent 的项目归属推理,
  且和"聊天=输入、面板=展示确认"的 IA 定调(07-11)相悖。留 v2。
- LLM 视觉分类图片:07-09 已裁决入口约定+问,不上视觉模型。
- 独立 intake MCP server:多一个进程不值;挂 organize server 职责同族。

## Test strategy (oracle)

- **py**(先红后绿+突变红检):规则表解析(默认+覆盖合并/未知扩展名=无建议);
  list_inbox(收件箱候选名容错/空箱/项目 token 唯一命中 vs 歧义留空);
  stage_intake(ops 构造/类目夹路径/suggest-only 类目照样可人工确认 stage);
  approve 针孔(非 json 拒/多余键拒/plan 不存在/已 applied/成功链路 audit 落盘)。
- **mjs**:收件箱卡片纯逻辑(pending plan 分组/预览行格式化/空态)。
- **e2e 真 gateway**:夹具收件箱丢 3 文件(参考图/dwg/未知扩展)→ GET /api/intake
  建议正确(dwg=suggest-only 无自动)→ 核心直调 stage → 卡片出预览 → POST approve
  → 磁盘文件真归位 + 卡片清空 + audit 有记录。
- **resolver eval**:新工具 docstring(「整理一下收件箱」「收件箱里有什么」)计分。
- **verify lane = full panel**(文件移动=数据安全 + 新 POST 写针孔),四腿首跑。
