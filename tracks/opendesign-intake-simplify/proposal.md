# Proposal: opendesign-intake-simplify

- Date: 2026-07-25
- Status: open

## Goal

清掉 2026-07-24 真机反馈里**碰服务端/写路径**的两条(前端 6 条已在
`opendesign-feedback-0724-ui` 归档):

- **#3 建档去掉「业主名(必填)」框** —— 未建档文件夹的建档小表单只填项目名。
- **#4「打开文件夹」要跳到最前** —— Windows 上资源管理器开在浏览器后面,
  新用户以为没反应。

## Motivation

两条都卡在"第一次用"的路上:建档是设计师接触这套东西的第一个动作,多一个必填框
就多一次卡住;「打开文件夹」点了像没反应,会让人怀疑整个工作台是不是坏的。
两条都不是锦上添花,是首用信心。

## 真问题(第一性)

- 用户原话:
  - 「项目建档表单仍显示『业主名(必填)』;直接去掉这个框,只填项目名称即可」
  - 「工作区点打开文件夹,资源管理器窗口开在后面,新用户以为没反应;
    点了把资源管理器窗口拉到桌面最前」
- 真正要解决的是:
  1. **建档这一步不该逼人填不知道的东西**。设计师拿到一个文件夹先建档,业主称呼
     可能还没定(或懒得打字);业主信息本来就有 `update_client` 可以后补。
     ⚠️ 但这不只是删一个 `<input>`:核心 `ds_tools.create_project` 现在
     `if not project or not client: return empty_name`,且骨架模板写死
     `- 业主: [[{client}]]`。空业主照原样写会变成 `- 业主: [[]]`,
     ds_lint 的 broken_link 判据会当断链 → **新档案自带一条体检报错**。
     正确做法:空业主时**整个链接不写**(`- 业主: `),与 `_CLIENT_TEMPLATE` 里
     `linked` 的既有写法同源。
  2. **「打开文件夹」的"完成"不是"进程起来了",是"用户看见了那个窗口"**。
     `os.startfile(path)` 只把请求丢给 shell,z-order 归 Windows 管;而 ds_web 是
     后台进程、不持前台权,**Windows 的 SetForegroundWindow 前台权规则会拒绝它抢焦点**,
     典型表现正是任务栏闪一下。所以这条的诚实结论是:**尽力而为 + 明确告知**,
     不能承诺 100% 置顶。
- 我在这中间翻译了什么:
  - 「去掉业主名框」→ 译成"核心允许空业主 + 空业主不写链接"。**没有**顺手把业主
    字段从骨架里删掉(那会让 list_projects / cockpit / ds_lint 全部变脸)。
  - 「跳到最前端」→ 译成"打开后尽力把那个资源管理器窗口提到前台,失败就退化成
    现在的行为"。**这条在 Linux 开发机上无法真验**,只能注入假 user32 验逻辑 +
    真机验收(deployment-target 铁律)。

## Scope

- in:
  - `bin/ds_tools.py` — `create_project` 允许空业主(空则不写 `[[链接]]`、不建 stub);
    MCP 工具签名/docstring 同步。
  - `web/src/workspace/ChangesColumn.tsx` — 删业主名输入 + 错误提示改口。
  - `bin/ds_web.py` — `_default_open_launcher` 的 Windows 分支加"尽力提到前台"。
  - oracle:`tests/test_ds_tools.py`、`tests/test_ds_web_api.py`、`tests/e2e/intake.e2e.mjs`。

## Non-goals

- 不删骨架里的 `- 业主:` 字段行(下游 list_projects / cockpit / ds_lint 都读它)。
- 不动 `create_client` / `update_client` / `rename_project` 的语义。
- 不给空业主自动补名(不猜业主叫什么 —— PKB 诚实性底线)。
- 不碰 open-folder 的任何安全闸,也不动 rel(开单文件)分支的行为。
- 不做模型接入界面(用户 07-24 明确说先不做,结论是开机向导而非网页框)。

## Risks

- **写路径 + PKB schema 触边** → verify 走 **full 四审**(新写口/数据一致性不打折)。
- `create_project` 放宽必填 = **注入面复核点**:client 仍须过 `sanitize_field`,
  空值走"不写链接"分支而非写空链接。
- Windows 置顶要 ctypes 调 user32,**绝不能阻塞 HTTP 响应**(ds_web 单线程),
  等窗口出现的重试必须丢 daemon 线程。
- 真机未验:置顶效果只能由用户在 Windows 上确认(验收清单必列)。
