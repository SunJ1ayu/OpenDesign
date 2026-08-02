# Design: opendesign-structure-debt

- Change: opendesign-structure-debt
- Status: draft(主 agent 方向已落盘,panel 未读)

> 本单**不是**真·开放架构分叉:两刀都是"东西放错位置、挪回去",方向唯一。
> 按 track 约定,**不为这两刀花 panel-explore**。
> 真正的开放问题是被划出 Scope 的第 ③ 刀(MCP 注册层),那个单独起 track 时再问。
> 但 verify 阶段仍走 panel-review(见 verify.md 的 lane)。

- 规划双出: **不适用** —— 触发条件是"新写面 / 开放方向"(动档案格式、写口语义扩张、
  新增参数)。本单**零行为改动、零新参数、零写口变化**,纯搬运,没有"我以为理所当然"
  的规格空间可言。⚠️ 若实施中发现某个函数不能原样搬(必须改签名/改行为),
  **那一刻本单的前提就破了** —— 停下来回来改 design,别在搬运单里顺手改设计。

## Approach

### 查证:两处循环依赖的真因(与我的第一印象相反)

第一印象是"两块业务互相要对方"⇒ 大手术。**打开文件看,是错的。**

**循环 ①(`ds_adopt` ⇄ `ds_organize`)—— 本单不做,但真因记在这里**
`ds_organize.py` 除了业务逻辑,**还兼职当"助手工具登记处"**:里面有 7 个
`@server.tool()`。其中 `adopt_workspace_tool` / `stage_adoption_tool` 转发给 `ds_adopt`
(`ds_organize.py:365` 的函数内 `import ds_adopt`)。
⇒ **循环不在业务层,在"登记处"层。** 全项目 29 个 MCP 工具散在三个业务文件里
(`ds_tools` 17 / `ds_organize` 7 / `ds_refs` 5)。抽出登记层,循环 ① 自动消失。
这就是第 ③ 刀,面广,划出 Scope。

**循环 ②(`ds_workspace` ⇄ `ds_intake`)—— 本单要消掉**
`load_taxonomy`(读那张"什么后缀算什么类目"的规则表)住在 `ds_intake` 里,
但 `ds_workspace.py:159` 要用它,只好函数内延迟 import,还写了段注释辩解。
实测**四个模块**都在用它:`ds_intake`、`ds_adopt`(:114/:189)、
`ds_web`(:662/1170/1275/1705/1807 共 6 处)、`ds_workspace`(:159)。
⇒ **taxonomy 是一张公共配置表,谁的也不是,却寄居在"收件箱"里。** 这是错位,不是耦合。

### 第 ① 刀:`bin/ds_taxonomy.py`

把 `ds_intake` 里 taxonomy 的**加载/查询**函数(`load_taxonomy`、`suggest_category`
及其私有辅助)整体搬到新模块 `bin/ds_taxonomy.py`,调用方改为 `import ds_taxonomy`。

- `ds_intake` 保留**薄转发**还是硬切?→ **硬切,不留转发。**
  理由:留转发就等于两个名字指同一件事,下次谁引哪个全凭手感,错位没消灭只是变隐蔽
  (记忆 [[memory-points-drawer-owns]] 同一类病:事实复制到第二个地方,只更新一个)。
  调用点一共 10 处,一次改干净。
- `ds_workspace.py:159` 的 `_load_taxonomy_for_skip` **连同那段延迟 import 的辩解注释
  一起删掉**,改成模块层正常 import。**注释必须删** —— 留着就是撒谎,
  而"注释撒谎"正是这个仓库已经记在账上的另一条债(`ds_web.py:597`)。

### 第 ② 刀:`bin/ds_openfolder.py`

`ds_web.py` 里这一整块与 HTTP 无关,是**操作系统交互**:
`_pick_folder_window`(294)/`_norm`/`_head`/`_win_folder_windows`(346)/
`_win_activate`(371)/`_win_focus_folder`(410)/`_spawn_win_focus`(446)/
`_open_windows`(458)/`_default_open_launcher`(534) —— 约 294–580 行。

- 路由方法 `Handler._open_folder`(1127,107 行)**留在 `ds_web`**:它是 HTTP 层
  (解析请求、鉴权、拼响应),只是把"真正去开窗口"这件事委托出去。**边界画在
  "HTTP 语义 vs 操作系统语义"上,不是按行数切。**
- 收益不只是瘦 14%:这块是全项目**最难测**的部分(要 mock 窗口枚举 + user32),
  独立成模块后可单独测、且它的 Windows-only 分支不再拖着整个 web 层。
- 已有判据兜底:`tests/test_ds_web_open_front.py`。

## Key trade-offs / risks

- **最大风险 = 搬运单里夹私货。** 纯搬运的 diff 会很长(几百行位移),
  人眼极易漏掉中间夹的一行真改动 —— 这正是闸③"亲读 diff"最吃力的形态。
  ⇒ 对策见下方 oracle 的"函数体逐字节不变"机械检查,**不靠肉眼**。
- Windows 那块我在 **Linux 上改、无法真跑**(`user32`/窗口枚举 Linux 没有)。
  单测是 mock 的,真行为只有用户 Windows 机能证。⇒ 列入真机待验,**不算已验证**。
- `ds_intake` 硬切不留转发 ⇒ 若漏改任一调用点,是 `AttributeError` 当场炸,
  不是静默错 —— 这是**好**的失败模式,比留转发安全。

## Alternatives considered

- **把 taxonomy 塞进 `ds_common`**:否。`ds_common` 已是杂物抽屉(87 行、被所有人依赖),
  往里塞等于把错位换个地方藏。taxonomy 有自己的语义,值得一个自己的名字。
- **按行数切 `ds_web.py`**(比如"超过 1500 行就对半分"):否。按行数切出来的边界
  没有语义,下次照样长回去。按"HTTP vs 操作系统"切,边界能自己维持。
- **先做前端**:否。风险直接落在用户眼前,且后端边界没站稳时前端拆了还要再动。
- **一次做完三刀**:否。第 ③ 刀值不值得做本身是开放问题,且它面广;
  和纯搬运混在一个 diff 里,闸③就彻底废了。

## Test strategy (oracle)

主 agent 拥有。**核心不是"功能还在",是"一个字都没改"。**

1. **O1 机械闸:函数体逐字节不变。** 搬运前把每个待搬函数的源码
   (`inspect.getsource`)存成基线哈希;搬运后对新模块里的同名函数重算,**必须全等**。
   这条是本单唯一挡得住"夹私货"的东西 —— 肉眼读几百行位移 diff 挡不住。
2. **O2 循环依赖真的消失**:一条脚本静态扫 `bin/ds_*.py` 的模块层 import,
   建图查环,**断言无环**;并断言 `ds_workspace.py` 里不再出现函数内延迟 import 的
   那段辩解注释。(不是"跑得通"就算 —— 跑得通是延迟 import 本来就保证的。)
3. **O3 全量回归**:py `unittest discover` 827 例 + `tests/e2e/run-all.sh` 31 例,全绿。
4. **O4 调用点全覆盖**:`grep` 断言 `ds_intake.load_taxonomy` / `ds_web` 里那 9 个
   Windows 函数名**在仓库中零残留**(硬切,不留转发)。

**这个 oracle 能被什么骗过?**

- **最可能被骗的形态:全绿但 Windows 上开文件夹坏了。** O1~O4 全是"代码没变/import 没环",
  没有一条证明**真机上那个窗口真的弹出来并切到前台**。Linux 上根本跑不了 `user32`,
  单测是 mock 的 —— **mock 绿只证明我搬对了调用,不证明系统调用还灵**。
  ⇒ 接得住它的只有**用户 Windows 机上真点一次「打开文件夹」**。列为真机必验项,
  在他验之前本单**不许宣布完成**(记忆:「在使用现场验证」,一周内栽过两次)。
- 第二个洞:O1 只锁**函数体**,锁不住**模块层常量/正则**被顺手改。
  ⇒ O1 补一条:两个新模块的模块层常量也进基线哈希。
- 第三个洞:O2 查的是"有没有环",查不出"边界画得对不对"。
  一个把所有东西塞进一个文件的方案也无环。⇒ 这条靠 panel-review 的人看,机械挡不住。
