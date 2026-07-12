# Tasks: opendesign-workbench-p5

- base-ref: c2fbe45ea4c78a8cbe3b65db0b535425a472349c

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [ ] T1 `bin/ds_workspace.py` + `tests/test_ds_workspace.py`(oracle 先行):
      workspace.json 解析/key→路径闸/类目扫描/图片列举;taxonomy v1.0 tmpdir 夹具
- [ ] T2 ds_web 三个 GET 端点(overview / images / file)+ api 契约与三闸红检测试
- [ ] T3 open-folder POST 受控例外 + 红检(未执行断言 / 其余写方法 405 不变量)
- [ ] T4 前端 CompanionColumn 真数据化(概览+打开按钮+未配置空态)
- [ ] T5 前端 GalleryPage 图墙(路由/筛选/lightbox)+ 纯逻辑 mjs oracle
- [ ] T6 e2e 真 gateway(Playwright:概览→图墙→筛选→lightbox)+ 全量回归
- [ ] T7 verify.md full lane(panel-review,先落主审)+ dist 构建 + 文档
      (install-windows.md 配置段 + SCHEMA/AGENTS 如涉及)
