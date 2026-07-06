# Verify: opendesign-workbench

- Date: 2026-07-06
- Verdict: **PASS**(主裁;full lane = 主 agent + MiMo PASS + GLM PASS +
  SenseNova BLOCK——其 BLOCK 主项已用解释器实证证伪,见仲裁)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## Mechanical checks

- [x] build passes(tsc -b + vite build,产物 148KB js + 3.2KB css)
- [x] tests pass(92/92:80 旧 + 2 collect + 10 ds_web;golden 逐字节不变)
- [x] no secrets / unsafe ops(服务只读只绑 127.0.0.1;写方法 405 焊死;
      不触 PKB 写路径;无新第三方 Python 依赖)
- [x] 视觉冒烟(Playwright 截图实检:墨侧栏+纸面主区+CAD 修订标签,
      两条真实样例项目渲染正确)

## Review

- lane: full(主 agent + MiMo + SenseNova + GLM;改动面含 ds_todo 核心重构)
- 主 agent 自审(先行落盘于 /root/aiwork/tasks/opendesign-workbench-p0-my-review.md,
  在读任何 panel 输出之前):PASS;自审抓到并已修 1 处 —— _static 读文件
  OSError 未接 500 路径(git pull 覆盖 dist 瞬间并发读会炸 handler 线程)。
  逃逸面(unquote 单次/反斜杠拒/realpath+within/symlink)核过;collect/render
  等价性由 golden 锁定 + FIELDS_RE 前缀同 OPEN_RE 推出 m 恒非 None。
- panel findings 与仲裁(日志 /root/aiwork/logs/panel-opendesign-workbench-p0.*):
  - **MiMo(agent 腿,PASS,8 条)——本轮质量最高,全库 15 文件读了实审**。
    采纳 5:F1 ds-web.ps1 补 `exit $LASTEXITCODE`;F2 install-windows.md §1
    手动 pip 步骤钉版本(与 install.ps1 对齐,Medium 实至名归);F3 Health 组件
    补 r.ok 检查;F5 symlink 逃逸测试变体;F6+F8 test_04 加 `assertNotEqual(200)`
    + install.ps1 补非阻断 `pip check`。拒 3:F4 前端运行时 schema 校验
    (同仓原子部署,MiMo 自己也判 P0 可接受)、F7 测试临时目录 addCleanup
    (全仓测试同惯例,只改新文件反而制造风格漂移)、O1 list_todos 仍走 render
    (设计如此:聊天要文本,render 即 collect 的壳)。
  - **GLM(PASS,2 条)**。#1 FIELDS_RE 防御检查:按"更优形式"采纳——不加
    防御分支,改成**删掉 OPEN_RE、FIELDS_RE 单正则做唯一闸门**,把"双正则
    漂移"这个缺陷类整个消灭(防御检查只是把崩溃变静默丢行,更糟);
    #2 "%5c%5c 绕过"证伪:`"\\" in raw` 是单字符成员判断,双反斜杠必然
    包含单反斜杠,Python 语义上不存在该绕过。
  - **SenseNova(BLOCK,6 条)——BLOCK 不成立**。#1 allow_reuse_address
    "默认 False"证伪:`http.server.HTTPServer` 类属性 = 1(解释器实证
    `ThreadingHTTPServer.allow_reuse_address == 1`),socketserver 默认值被
    子类覆盖,其引用的文档对象错了;#2 SPA fallback 缺失证伪:前端就是
    hash 路由(App.tsx fromHash / href="#/..."),它自述看不到 web 源码,
    属盲区推测;#4 Python 3.10+ 未声明证伪:install-windows.md §0 第一行
    就写着"Python 3.10+";#6 BOM 兼容 PS2.0 拒:基线 PS5.1,BOM 是 7-03
    真机乱码教训的修复,删了才是回归。采纳 2:#3 405 补 `Allow: GET`
    (RFC 7231)、#5 test_04 反斜杠变体收紧为精确 400。
- 修复后复验:npm build 重构建(App.tsx 变更)+ 92 测全绿。
- arbitrated verdict (主裁): **PASS** —— 三方无一抓到阻断级缺陷;主 agent
  自审的 _static OSError 洞仍是本轮唯一真 bug,且在 panel 前已修。

## Accepted deviations

- HEAD 请求走 http.server 默认 501(浏览器页面导航不用 HEAD,无害)。
- 静态文件整读进内存(dist 最大 148KB,本地单用户,无害)。
- /api/health 暴露 ds_root 绝对路径(仅 127.0.0.1 可达,排查便利,接受)。
- ds-web.ps1 / install.ps1 钉版本行真机 UNTESTED(惯例=下次装机/gitpull 即验收;
  install-windows.md §5b 已带自测命令)。
- mcp==1.28.1 与 nanobot-ai==0.2.2 成对钉死 = 开发机实测组合;未跑 pip check
  (待 panel/装机印证)。
- Windows 写锁窗口内并发读 = 瞬时 500,刷新自愈(design D2 已显式接受)。
