# Tasks: opendesign-clickable-actions(P0 前两项:记一条 + 建档 变直接点)

- base-ref: (本 track 立项 commit)

> 模型分层试跑**第三单,执行腿换 Sonnet 5**(前两单 Opus)。主 agent 写 oracle 先行
> (tests/test_ds_web_api.py 两个针孔契约类,已红);Sonnet 5 worktree 承包实现;
> oracle off-limits;verify fast lane(受控写针孔,非脊梁级)。roadmap 见
> docs/frontend-actions-roadmap.md。#3 收件箱扫描按钮下一 track(要新核心函数)。

- [ ] T1 后端针孔 POST /api/changes/add {project,content,space?} → ds_tools.append_change
      (posture 逐条同 _edit_change:CT json/body≤OPEN_BODY_MAX/JSON dict/键白名单/类型闸;
      错误映射 empty_content→400 project_not_found→404 no_change_section→409;精确匹配)
- [ ] T2 后端针孔 POST /api/projects/create {project,client,stage?,address?} → create_project
      (同 posture;empty_name→400 bad_stage→400 project_exists→409;client 必填)
- [ ] T3 前端:ChangesColumn 顶部"+ 记一条"快捷输入(content + 可选空间;回车/按钮提交
      addChange;成功 onEdited 刷新;busy/空内容禁用);复用暖纸面样式
- [ ] T4 前端:未建档空态(ChangesColumn unregistered 分支)+ Sidebar"+"→ 建档小表单
      (项目名预填文件夹名 + 业主名必填输入)→ createProject;成功选中新项目
- [ ] T5 版本 0.28.0;py 回归(oracle 两类全绿 + 全套)+ build;e2e 一条(建档→记一条→GET 见)
- [ ] T6 verify fast lane(主审 + submimo)
