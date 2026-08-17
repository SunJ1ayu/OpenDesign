# Tasks: opendesign-shell-chrome

- base-ref: df75738e6d6fdb72f9f9b8abd1558895e94c344b

> 判据(oracle)主 agent 亲写、**先单独 commit**,再 commit 实现。
> 勾是给下一个接手的人看的收据,不是进度条 —— 没跑完不许打(08-17 半截收据的账)。

- [ ] T1 判据先行:`test_shell_window.mjs` s-w1/s-w2 改写(病根标本)
- [ ] T2 判据先行:`test_shell_window_contract.py` x10 新增(跨语言标记对表)+ x4 补强
- [ ] T3 判据先行:`tests/e2e/shell_chrome.e2e.mjs` 新增(A 病本身 / B 浏览器 / C 命中测试 / D 不被盖)
- [ ] T4 红检(对照组):T1~T3 在**未修的 HEAD** 上跑,确认红在这个病上;单独 commit
- [ ] T5 实现:`shellWindow.ts` 地址标记 + `ds_shell.py` 常量与 URL + `WindowChrome.tsx` 注释纠错
- [ ] T6 亲跑全量:python 全套 / 全部 mjs / tsc / build / e2e 总跑(0 跳过)
- [ ] T7 verify:lane 判定 + panel + 主裁
- [ ] T8 bump 0.91.0 + 编安装器 + 发 pre-release + 回读远端 digest 对字节
- [ ] T9 真机清单-0.91.0(合并 0.90 的 A~D 与 0.89 的 A~G,一趟走完)
- [ ] T10 归档 + push + 回读远端确认
