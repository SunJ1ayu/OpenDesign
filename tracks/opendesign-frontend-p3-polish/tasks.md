# Tasks: opendesign-frontend-p3-polish

- base-ref: e5bac70037dfd54774aa037d7a2fcbdf66ab17f1
- 执行腿:sub Claude worktree(AGENTS.md Tiered execution);oracle 主 agent 亲写并先 commit

## T0 — oracle 先行(主 agent,DONE)

- [x] `tests/test_ds_web_open.py`(I4 后端安全闸,14 用例)
- [x] `tests/test_project_name.mjs`(I6 显示名 + I4 前端分流纯逻辑)
- [x] `tests/e2e/frontend_p3_polish.e2e.mjs`(I1/I2/I3/I4/I6 UI 事实)
- [x] red-check:py 9/14 红、mjs import 失败红、e2e I6 红 —— 均因"未实现"而红,
      夹具健康度已单独验证(括号夹被发现为未建档、recent 含 .dwg/.bat)

## T1 — I4 后端受控开口拓宽(安全面,先做)

- [ ] `bin/ds_web.py`:`_OPEN_EXTS` 白名单常量 + `_open_folder` 支持 `rel`
      (Gate A relpath_ok → Gate B realpath+within → Gate C 扩展名 → Gate D isfile);
      `rel`/`sub` 互斥 400;白名单外 415;**任何拒绝路径零 `OPEN_LAUNCHER` 调用**
- [ ] oracle:`python3 tests/test_ds_web_open.py` 全绿

## T2 — I4 前端 + I6 纯逻辑

- [ ] 新建 `web/src/workspace/projectName.ts`:`displayProjectName` / `openTargetFor` /
      `OPEN_FILE_EXTS`(与后端白名单同集合)
- [ ] `web/src/api.ts`:`openFile(key, rel)`(复用 `/api/open-folder`,带 `rel`)
- [ ] `web/src/workspace/CompanionColumn.tsx`:recent 行 `<div>` → `<button data-ui="recent-row">`,
      按 `openTargetFor` 分流,`title` 显 `类目/文件名`
- [ ] oracle:`node --test tests/test_project_name.mjs` 全绿

## T3 — I1 / I2 / I3 / I5 / I6 视图层

- [ ] I1 `GalleryPage.tsx`:「来源」`<Chips>` → `<select data-ui="gallery-source">`,
      挪进标题行,选中显来源名 + × 清除;空间/风格两组 chip 不动
- [ ] I2 `ChangesColumn.tsx`:建档按钮 `.btn-save` → `.btn-primary`
- [ ] I3 `app.css`:`.aside` 290→400px、`.chatcol` 340→300px;`.thumb-grid` 2→3 列;
      `CompanionColumn` `showMore` 阈值 3→5
- [ ] I5 `ChatPage.tsx`:`.chat-meta` 降噪 10.5px/`--ink-5`;「退出登录」收进 `…` 菜单
      (复用设置弹层卡片样式,esc/外点关闭),去掉内联 style
- [ ] I6 `app.css` `.proj-row .nm` 两行截断;`Sidebar.tsx` 用 `displayProjectName`,
      `title` 拼「完整原名 + 原有补充」
- [ ] `bin/ds_web.py` VERSION → `0.32.0`;`npm run build` 重建 dist

## T4 — 收货(主 agent 亲做,执行腿自述一概不作数)

- [ ] 闸①:oracle 三文件对 T0 commit **逐字节 diff 为空**
- [ ] 闸②:主 agent 亲跑 oracle + 全量回归(pytest / 全 mjs / build)+ `/api/health` 回显 0.32.0
- [ ] 闸③:主 agent 亲读 diff(I4 安全面逐行)
- [ ] verify:**full 四审**(新写口/权限面不打折)→ 仲裁 → 修 → merge → 归档

## 执行腿铁律(派活 prompt 必带)

1. `tests/test_ds_web_open.py`、`tests/test_project_name.mjs`、
   `tests/e2e/frontend_p3_polish.e2e.mjs` **逐字节 off-limits**,一个字符都不许动。
2. 自检清单:三份 oracle + 全量回归 + build 全绿才交。
3. 不 push、不 merge、不归档、不装依赖。
4. 白名单是安全边界:**绝不允许**为了让某个用例过而往 `_OPEN_EXTS` 里加可执行/脚本/
   快捷方式扩展名。
