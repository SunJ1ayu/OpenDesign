# Tasks: opendesign-windows-installer

- base-ref: c24a3b5a42be23b7f1adcd7bc9a6846ff4bd50d7

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 派给

**S0 全部主 agent 自己干,不派腿。** 理由不是"腿不行",是这单的工作量几乎全在
**判据本身**(spike.py 就是 oracle),而 oracle 永远不外包。剩下的是打包动作,
比写任务书还短。S1 造安装器时重新评估分层。

## S0 —— 探路包(回答:免装 Python 跑不跑得动)

- [x] 摸底:向导可被脚本替代(探针 6/6 + 我补强的判据 C 两问)
- [x] 摸底:119 依赖全部有 Windows 轮子、0 源码包
- [x] 摸底:离线装配 payload 成立(rc=0,355MB)
- [x] 摸底:embeddable Python 3.12.10 存在且版本对得上
- [x] 写 `spike.py`(判据本体,六问 + 七个防骗焊点)—— 已单独 commit(`0eed36e`)
- [x] 判据自己先在 Linux 台架上跑通(真起网关、3 个 MCP 全连上、ds-web 自报 0.85.0);
      **跑的过程中判据自曝一个 bug**:`inside_root` 用 `resolve()` 跟穿软链接 ⇒ 会假红,
      已修(`8227223`)。29 PASS / 2 FAIL,两条红都是台架≠真包的真实差异。
- [x] 红检:六条变异逐条指定靶子,**6 咬住 / 0 漏网**(`mutation-test.sh`)
- [x] 组包:embeddable 3.12.10 + `._pth`(放开 site + 写死 `..\ds\bin`)+ 119 包 payload
      + ds 文件 + `跑一下.bat`(CRLF)
- [x] 本机能验的部分验掉(`check-package.sh`,0 条不合格):无 Linux `.so` 泄漏、
      86 个 `.pyd`、`._pth` 三项、关键包齐、版本号锚一致、无字节码残留
- [x] 出 zip:**79MB**,回读校验无坏文件,6 个关键入口逐个点名在
- [x] **业主真机跑一趟** —— 两跑:第一跑红在 Windows 专属依赖被静默丢掉(根因见 verify F1),
      补齐后**第二跑 31 PASS / 0 FAIL / 0 SKIP 全绿**。两份收据都在 `evidence/`。
- [x] **S0 结论:免装 Python 跑得动。** 运行时形态定为 embeddable,退路不必再走。

## S1 —— 安装器(业主 08-12 夜已把该拍的都拍了;08-13 开工)

> 👉 **明天从这里接**:先跑规划双出(下一条),别直接写 NSIS/Inno 脚本。
> 该问的产品问题业主都答完了,答案在 design.md「业主已拍板的」那一节,别再问一遍。

- [ ] **规划双出**(设计要点见 design.md,S1 命中触发条件,不许省)
- [x] 定:运行时形态 = **embeddable**(S0 真机全绿,已定)
- [x] 定:更新路径 = **应用内提示 + 一键更新**,源用 GitHub Releases,分两层下
      (代码 1.1MB 常更 / 运行时 269MB 极少动),要能回滚,数据不碰
- [x] 定:key + 口令 = **装完第一次打开时问**(安装器全程不经手凭据)
- [ ] 安装器脚本(倾向 **Inno Setup**,VS Code 同款;NSIS 备选)+ 在本机构建 .exe
- [ ] 桌面外壳:自己的窗口 + 托盘常驻 + 关窗口不退出(**这层会引入新的仅 Windows 依赖
      ⇒ 必须先进探路包再跑一趟真机**,别直接写进安装器)
- [ ] 首次启动向导:问 key + 登录口令
- [ ] 应用内更新:查版本 / 只下 1.1MB 那层 / 失败回滚
- [ ] 砍 AWS 那 32MB(**聊天平台 9MB 全留 —— QQ 在里面**)
- [ ] 卸载、开始菜单、桌面图标
- [ ] verify(lane 见 verify.md;**碰装机/权限/key ⇒ 预计 full**)
