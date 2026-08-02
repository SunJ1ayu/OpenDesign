# Design: opendesign-todo-ux

- Change: opendesign-todo-ux
- Status: draft

> 非开放架构分叉(既定 UI 快修),不跑 panel-explore。方向直接落。

## Approach

四条改动都落在待办页(TodoPage),后端不动、复用现有 `/api/changes/edit` 写针孔。

### A1 状态一键改(#3)
- `st-pill` span → button。点击开一个**状态快捷菜单**(仿 `.settings-pop` 定位/层级模式:
  absolute 挂在行内、点外收起)。菜单列四状态,当前态标记;选一个 → 走 `buildEditRequest(it, {status})`
  → `editChange`,不进编辑态。
- **显眼度分级(复核修正)**:菜单里「进行中」正常显眼;「已完成/已关闭」放次级(小一号/靠下/需明确点),
  降低手滑直接落终态。
- 「编辑」按钮保留,只管改正文/加备注。

### A2 撤销 toast(#4,与 A1 同单元)
- 快捷菜单/编辑把状态改到**终态(已完成/已关闭)**后:因该项会离开 `/api/todos`,弹一个**页面级 toast**
  「已标记『X』· 撤销」。
- toast 态**独立于列表数据**存(快照 `{project, cnum, label, prevStatus}`);列表随后重拉、该项消失不影响 toast。
- 撤销 = `editChange({project, cnum, new_status: prevStatus})` → 清 toast → 重拉。
- 非终态变更(待确认↔进行中)项目仍在页面,无需 toast。
- toast 自动消失(~6s)或手动关;`prevStatus` 取自变更前的 OpenItem(可靠)。

### A3 备注乐观回显(#2)
- 编辑保存带 note 后:除现有 `edited`(看原文)外,再记一个 `noted: editId→note`,行内显示一条
  「备注:…」(样式仿 `edited-tag`)。持久留痕仍在工作台变更列(/changes 带 history),不扩 /api/todos。

### A4 状态含义(#1/#5)
- pill 与快捷菜单项加 `title`/提示:待确认=「等业主确认」、进行中=「我在做」、已完成=「做完了」、
  已关闭=「作废/取消」。纯文案,数据不动。
- `workspace/AGENTS.md`:补一段状态语义——业主提了没最终敲定→待确认;敲定/开工→进行中;
  作废用已关闭。教 agent 按"球在谁"设状态。

### 纯逻辑(todo.ts,oracle 直测)
- `isTerminalStatus(s)`:s∈{已完成,已关闭}。决定是否弹 toast。
- `STATUS_HINT: Record<Status, string>`:状态→含义短语,UI 与测试同源。

## Key trade-offs / risks

- **乐观回显 vs 单一真相源**:备注/看原文是本会话乐观态,刷新即失;持久真相在 .md 变更历史段
  (工作台变更列可见)。有意不扩 `/api/todos`(collect 单一真相源,爆炸面大)——延续 todo-edit 的 accepted deviation。
- **撤销窗口**:toast 关掉后要改回得去项目视图(=#7 第一刀,本组外)。可接受:toast 覆盖"手滑立刻改回"这一主诉求。
- **一键落终态的手滑**:靠菜单里终态次级显眼度 + 撤销 toast 双重兜底。

## Alternatives considered

- 扩 `/api/todos` 带 note/history 让备注持久显示:否——爆炸面大、破坏 collect 单一真相源,乐观回显已够。
- 做「已完成」折叠区放本组:否——无项目级视图它无家,归 #7 第一刀(复核结论)。

## Test strategy (oracle)

- mjs(`tests/test_workbench_p4.mjs`,先红后绿):`isTerminalStatus` 四状态判定;`STATUS_HINT` 覆盖四状态且非空;
  `buildEditRequest` 现有契约不回归。
- py:后端写口径不变,`test_ds_web_api.py`/`test_ds_tools.py` 现有套件保持绿(无新端点)。
- e2e(真起 ds_web):点 pill 改状态→列表更新;改到终态→toast→撤销→项恢复;编辑加备注→当场显示。
- 部署目标:真机 git pull + rebuild,页脚回显新版本 0.10.0。
