# Design: opendesign-cockpit(合并版 plan,2026-07-17 冻结)

- Change: opendesign-cockpit
- Status: final(主 agent 独立 plan × sub Claude 独立 plan 合并;两版都 no-new-page,
  分歧逐条仲裁见尾部「合并记录」)

## 方向

升级伴随列(290px)为驾驶舱列;图墙页 = 驾驶舱的"放大镜"。不动 C 位,不开新页面
(四列 min-width 1150px 无第五块预算;新路由会把"进项目即见"藏进一次点击)。

## 信息架构(伴随列自上而下)

| 块 | 内容 | 数据 |
|---|---|---|
| ① 项目速览(新) | 阶段 chip(空不渲染)· 业主 · 当前状态一句 · 最近更新 | /api/projects 现有 stage/last_update + **新增 owner(剥[[]])/status_note**;unregistered 显「未建档」 |
| ② 图片(改) | tab「参考/项目图」:项目图=全部工作区图 mtime 降序+类目小标;**删 includes("效果图") 硬编码**;「图墙 →」块头常驻(修 0~3 张图无入口的可达性洞) | refs + files/images(零后端改动) |
| ③ 项目文件(改) | 类目行=名+计数+**活跃度**(类目最新 mtime 相对时间;capped 类目置 null 不显示——名序截断后 max 不可信,宁缺勿假) | files/overview,categories **新增 latest_mtime** |
| ④ 最近更新(现状) | recent 8 保留 | overview.recent |

侧栏顺手偿债:depth2 已建档条目补 group(Sidebar 已渲染 p.group,只差后端字段)。

## 后端最小增量(全 GET,405 零触碰)

1. ds_workspace.overview:categories 加 latest_mtime(扫描已握 mtime,零额外 IO;
   capped→null)。
2. ds_web._projects:已建档条目加 owner(_field "业主" 剥[[]])/status_note
   (_field "当前状态");depth2 时用 consumed 循环的 realpath ↔ project_folders
   `组:名` 映射补 group。
3. VERSION 0.24.0。

## 前端切分

- 新纯逻辑 web/src/workspace/cockpit.ts(零 DOM,mjs oracle):ownerLabel /
  projectImages(mtime 降序,与 gallery 同口径)/ categoryRows(活跃度串)/
  cockpitState(unconfigured/unmapped/unregistered/ok 四态状态机,组件只 switch);
  relTime 输入类型(ISO vs epoch 秒)在此收拢单一函数,防两处漂移。
- CompanionColumn 按四块重排;接 dataEpoch+route props(每轮聊天后重拉,
  仅 workspace 路由可见才拉,防隐藏列白扫——补 M5 缺口)。
- GalleryPage 空态文案去模板名("06-效果图"→"项目文件夹里的图片会自动出现");
  其余不动。App.tsx 传参;api.ts 补类型。

## 降级矩阵

unconfigured→接入表单(不动)/ mapped=false→关联引导(不动)/ unregistered→
速览「未建档」②③④照常 / 任意类目名→②③④天然泛化,全库不再有模板名硬编码。

## 风险(verify 要复查)

- mtime 不可信(网盘同步/复制会改写)→ 活跃度是"信号"不是"真相",capped 置 null。
- 扫描成本:dataEpoch 接入后每轮聊天多两次全树扫(每类目 2000 顶)→ 路由门缓解,
  不预优化,verify 记录真机观感。
- 图片带 lazy 加载顶住大量图(P5 既有取舍)。

## Test strategy(oracle 先行)

T1 py:test_ds_workspace 扩展(latest_mtime 正常/空类目/capped=null)先红→实现。
T2 py:test_ds_web_api 扩展(owner/status_note/剥[[]]/缺字段空串;depth2 group
   命中×显式映射×depth1 无字段;**405 不变量重申**)先红→实现。
T3 mjs:test_cockpit.mjs 先红→cockpit.ts(判卷用例:非模板类目名"渲染输出"全链路可见)。
T4 组件层+build 绿。
T5 e2e 真 gateway:登录→进项目→速览可见→项目图 tab→「图墙→」常驻入口→lightbox;
   夹具补一个非模板类目目录验降级。
T6 全量回归+红检(latest_mtime/剥括号改坏必红)+dist 进仓+verify(fast lane)。

## 合并记录(谁贡献了什么/谁被推翻)

- sub 推翻主 plan ①:类目按 taxonomy 模板顺序模糊匹配 → **弃**。模板名启发式
  正是"照现状认"的违规方向;名序天然吃到用户 01-/02- 前缀。反而要**拔掉**既有
  includes("效果图")(sub 抓的在案债,主 plan 漏)。
- sub 推翻主 plan ②:/api/projects 加 stage → **不需要**,字段早已存在(主 plan
  没核代码,sub 核了)。
- sub 推翻主 plan ③(降级为 follow-up):交付快照块 → 需类目名启发式+新端点,
  推迟到首装采纳引擎给出类目真相。
- 主 plan 贡献:阶段 chip 的产品动机(set_stage 同日落地,阶段成活数据)、
  图墙项目预选(记 follow-up)、fast/full lane 论证。
- sub 独有贡献:owner/status_note 速览、latest_mtime 活跃度、dataEpoch 刷新缺口、
  图墙可达性洞、depth2 group 偿债、mtime/capped 诚实置 null、relTime 类型收拢。
