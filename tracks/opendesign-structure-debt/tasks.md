# Tasks: opendesign-structure-debt

- base-ref: 5e13c9b8e1adda5d6b948417825f2e3bdeb3b87f
- 交付到:**ds-web 0.71.0**(bump 挂本 track,满足 track-guard)

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 判据(主 agent 亲写,**先单独 commit,再 commit 实现**)

- [ ] **O1 `tests/test_structure_moves.py`** —— 搬运保真闸(本单唯一挡得住"夹私货"的东西)
      - 待搬函数的**源码逐字节基线**存档(搬前生成,进仓库);搬后对新模块同名函数
        重算并断言全等
      - 模块层常量/正则也进基线(design 记的第二个洞)
      - ⚠️ **基线必须在搬运之前生成并单独 commit**,否则它只是"实现的复印件"
- [ ] **O2 `tests/test_no_import_cycles.py`** —— 静态扫 `bin/ds_*.py` **模块层** import
      建图查环,断言无环;并断言 `ds_workspace.py` 不再含"函数内延迟 import"那段辩解注释
      - 红检:当前树上跑必须**红**(现在有 2 个环),否则这条判据是假的
- [ ] **O3 `tests/test_no_stale_refs.py`** —— 硬切无残留:
      `ds_intake.load_taxonomy` 与 9 个 Windows 函数名在 `bin/` + `web/src` 零残留
      (转发也算残留 —— design 决定不留转发)

## 实现

- [ ] **T1 第 ① 刀:`bin/ds_taxonomy.py`**
      从 `ds_intake` 搬出 taxonomy 加载/查询;10 处调用点改名;
      删 `ds_workspace._load_taxonomy_for_skip` 及其辩解注释,改模块层 import
- [ ] **T2 第 ② 刀:`bin/ds_openfolder.py`**
      搬 `_pick_folder_window`/`_norm`/`_head`/`_win_folder_windows`/`_win_activate`/
      `_win_focus_folder`/`_spawn_win_focus`/`_open_windows`/`_default_open_launcher`
      (ds_web.py 约 294–580);**`Handler._open_folder` 留在 ds_web**(HTTP 层)
- [ ] **T3 bump 0.71.0**(挂本 track)

## 验收

- [ ] **G1** 全量回归:py 827 例 + `tests/e2e/run-all.sh` 31 例,主 agent 亲跑
- [ ] **G2** panel-review(lane 见 verify.md);主 agent 先独立审并落 findings 再读 panel
- [ ] **G3 ⚠️ 真机必验(在用户 Windows 上,主 agent 无法代跑)**:
      点一次「打开文件夹」,资源管理器**真的弹出并切到前台**。
      Linux 上 `user32`/窗口枚举根本跑不了,单测是 mock 的 ——
      **mock 绿只证明我搬对了调用,不证明系统调用还灵**。
      **他验之前本单不许宣布完成**(「在使用现场验证」,一周内栽过两次)。
