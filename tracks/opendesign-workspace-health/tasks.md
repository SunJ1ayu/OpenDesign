# Tasks: opendesign-workspace-health

- base-ref: 6a5913ae54e36915f00be2028144eaf51a150ad3
- oracle 基线: 本 commit(两份 oracle 已红检入库)

> 派活铁律:oracle 由主 agent 亲写,executor **off-limits**。派活时两份判卷文件
> 必须全部列进 `--protect` —— 守卫的强度只等于那份清单,漏列一个就是那个洞。
> 弱模型最可能的失败方式是**改考卷让自己及格**(删断言/写死期望值/加 skip)。

## 判卷文件(--protect 清单,一个都不许漏)

- `tests/test_ds_workspace_config_lock.py`
- `tests/test_ds_web_folder_visibility.py`

## 阶段一:并发锁(准入条件,先跑绿再谈体检卡)

- [x] T0 主 agent 写 oracle 一 `tests/test_ds_workspace_config_lock.py` + 红检
      (14/14 红;t05/t05b 是打在**当前真 bug** 上的红,不是 AttributeError)
- [x] T1 实现 `ds_tools.locked_workspace_json(ds_root)` 加锁读改写公共件
      - 契约见 oracle 的 `LockedWorkspaceJson` docstring
      - **锁必须活过 `os.replace`**(旁挂锁文件;锁在目标文件上会留在被 unlink 的旧 inode)
      - **锁必须跨进程**(真机是 MCP server + ds-web 两个进程;`threading.Lock` 等于没锁)
      - 复用 `ds_lock.exclusive`(跨平台已有件),别再造第二把锁
- [x] T2 修 `_write_workspace_json` 的**固定 tmp 名** —— 并发下会交错写同一个临时文件,
      导致 `FileNotFoundError` + 配置被写成非法 JSON。tmp 名唯一化
- [ ] T3 四个写口全部接到锁上,**一个都不许漏**:
      `set_workspace` / `bind_project` / `rename_project` / `delete_project`
      (读也要在锁内 —— 光把写包起来还是丢更新)
- [x] T4 oracle 一 全绿 + 全量回归绿 → 独立 commit

## 阶段二:体检卡本体

- [x] T5 主 agent 写 oracle 二 `tests/test_ds_web_folder_visibility.py` + 红检(28/28 红)
- [ ] T6 服务端读口 `GET /api/workspace/health`
      - 下发集合 = 根下可见一级目录 ∪ 已声明但当前不存在的名字
      - 每行:`reason`(declared/guessed/default)+ `currentlyHidden` + `preselect` + `missing`
      - `reviewId` 绑「配置内容 + 目录快照」
      - `applicable=false`(projects_root != root)时不出确认区
- [ ] T7 服务端写口 `POST /api/workspace/folder-visibility`
      - posture 照抄既有写针孔⑨/⑭;键白名单 `{review_id, hidden}`
      - 名字只能来自本次下发集合;快照变了 → 409 `stale_review`
      - 只动 `structuralDirs`,其余键原样保留;**走 T1 那把锁**
- [ ] T8 前端卡片,入口取代 `web/src/workspace/Sidebar.tsx:208` 的被动提示
      - 措辞只能是「显示 / 不显示在项目列表」,**绝不能**说成「设为收件箱」(盲点①)
      - 保存前给一句结果预览
- [ ] T9 oracle 二 全绿 + 全量回归绿 + build 绿 → commit

## 收货三闸(执行腿自述一概不作数)

- [x] 闸① 对 oracle 原始 commit 逐字节 diff = 空
- [x] 闸② 主 agent 亲跑 oracle + 全量回归 + build
- [x] 闸③ 主 agent 亲读 diff(安全面逐行;盯 `create mode 120000` 符号链接)

## 验收(**接口全绿 ≠ 做对了**)

- [ ] **真机回显**:用户机器 `git pull` → `bin\start.ps1` stop/start → Ctrl+F5 →
      `/api/health` version 对得上(盘上和运行时对不上 = BLOCK,不是警告)
- [ ] **真机肉眼**:拿真实工作区(含中文名、含一个没声明过的真项目文件夹)开卡片,
      确认那个真项目出现在「显示」侧 —— design「这个 oracle 能被什么骗过」点名的
      唯一接不住的错(下发集合算漏一个 → 接口全绿而文件夹从此消失)
