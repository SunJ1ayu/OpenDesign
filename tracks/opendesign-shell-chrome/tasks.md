# Tasks: opendesign-shell-chrome

- base-ref: df75738e6d6fdb72f9f9b8abd1558895e94c344b

> 判据(oracle)主 agent 亲写、**先单独 commit**(`037a393`),再 commit 实现(`4f4f5c0`)。
> 勾是给下一个接手的人看的收据,不是进度条 —— 没跑完不许打(08-17 半截收据的账)。

- [x] T1 判据先行:`test_shell_window.mjs` s-w1/s-w2 改写 + s-w2b/s-w2c(病根标本)
- [x] T2 判据先行:`test_shell_window_contract.py` x10(跨语言标记对表,**直接调
      `window_url()`**)+ x11(分界不许再读 pywebview)+ x12(问 Python 前要等 api)
- [x] T3 判据先行:`tests/e2e/shell_chrome.e2e.mjs` A/B/C/D 段
- [x] T4 红检(对照组):未修的 HEAD 上 11 条红、B 段绿
      (`evidence/20260817T135531Z-01-redcheck-e2e-unfixed-head.txt`;
      前两遍一份量具坏了、一份只有汇总,都留着没删,verify.md 里逐条说了)
- [x] T5 实现:`shellWindow.ts` 地址标记 + `ds_shell.py` 的 `window_url()` +
      `WindowChrome.tsx`(注释纠错 + 挂载时那问改成等 `pywebviewready`)
- [x] T5b 变异对照组:`inDesktopShell` 退回旧问法 ⇒ e2e 11 红 / mjs 2 红 / x11 红
- [x] T6 fast lane 评审(subdeepseek 单腿 PASS + 4 findings)+ 逐条仲裁
      → 采纳 F1(e2e 新增 E 段:真点按钮/真按把手,断言叫到了对应方法)
      + F3(x5 补两种全屏遮罩写法,对照组旧闸 0 咬 2 漏)
- [x] T6b E 段第一次跑就挖出 **D1:右上角斜角改不了大小**(按钮压过把手,0.89 的决定)
      ⇒ 钉进判据 + CSS 注释 + 真机清单 B7/F4,取舍摆给业主
- [x] T7 bump 0.91.0
- [x] T11 真机清单-0.91.0(把 0.89 的 A~G 与 0.90 的 A~D 合并成一趟)
- [ ] T8 总跑五段(最终代码 + 活 gateway,要 **0 跳过**)—— **跑着,没完不打勾**
- [ ] T9 编安装器(`OpenDesign-Setup-0.91.0.exe`,闸全绿)
- [ ] T10 发 pre-release `win-installer-0.91.0`(**回读远端确认** state=uploaded +
      远端 digest 与本地构建逐字节一致)
- [ ] **业主真机**:B 组(三个按钮 + 拖动带)是这一趟的主角
- [ ] T12 归档 + push + 回读远端确认
