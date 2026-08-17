# Proposal: opendesign-shell-chrome —— 窗口栏在真机上整块没画出来

- Date: 2026-08-17
- base-ref: df75738e6d6fdb72f9f9b8abd1558895e94c344b(0.90.0 归档那一笔)

## 业主原话(2026-08-17,装完 0.90.0 之后)

> 「1、这个页面为什么我拖不动 现在是固定住了吗 2、右上角还是没有缩小放大和退出」

## 现象 = 一个病,不是两个

0.89.0 把系统标题栏去掉了(`frameless=True`),约定三件事由我们自己画/自己接:
右上角三个按钮、顶部 30px 的拖动带、八个边角把手。**这三样在业主机器上一样都没出现。**

- 「拖不动」= 拖动带(`.win-bar`)没在场,而系统那条已经被我拿掉了 ⇒ 窗口确实动不了;
- 「右上角还是没有」= 那三个按钮没在场。

`WindowChrome` 在"我不在外壳里"这个判断下会 `return null`,一次性把这三样全撤掉 ——
业主看到的正是这个 `null`。

## 根因(源码级已核实,不是推测)

`WindowChrome.tsx:35` 只在**挂载那一瞬间**问一次"我是不是在外壳里",依据是
`window.pywebview.api` 在不在(`shellWindow.ts:37`)。那行注释写着
「pywebview 的注入发生在页面加载那一刻,之后不会变」——**这句是错的**。

pywebview 5.4 的 Windows 后端(EdgeChromium)在
`webview/platforms/edgechromium.py:314` 的 **`on_navigation_completed`** 里才调
`inject_pywebview(...)`,而那个回调在**页面自己的脚本跑完之后**才发生;
`webview/util.py:218` 还要再起一个线程注 `finish.js`(它才 `_createApi` + 派
`pywebviewready` 事件)。也就是说 React 挂载的那一刻,`window.pywebview` **必然不存在**。
⇒ 那一问永远答 false,窗口栏**永远**不画。pywebview 自己提供 `pywebviewready`
事件正是因为这件事,我当时没读它的源码。

(证据:`pip download pywebview==5.4` 的 sdist,本地解开逐行读。收据见 evidence/。)

## 为什么一整套判据一条都没响

现存 12 条判据(`test_shell_window.mjs` 3 条 + `test_shell_window_contract.py` 9 条)
问的全是「两边的名字对不对得上 / 层号对不对 / 把手贴不贴边」。
**没有一条问过「这条栏到底会不会被画出来」** —— 而那需要一个跑得起来的浏览器,
当时的判断是"要 pywebview,Linux 上验不了",于是整件事推给了真机清单 A~G,
那趟业主一直没走。这一单要把这个洞补掉:**让"会不会画出来"变成 Linux 上答得了的问题。**

## 目标

1. 无边框窗口在业主机器上**第一帧**就有:三个按钮 + 拖动带 + 八个把手。
2. 「会不会画出来」有真浏览器判据咬着,不再只靠真机清单。
3. 分界不许再依赖 pywebview 的注入时机。

## 非目标

- 不动窗口按钮的**行为**(最小化/最大化/关闭/拖动/改大小的原生实现一字不改);
  它们本来就只有真机答得了,这一单不碰。
- 不重做窗口栏的样子(高度、配色、图标)。
- 不追 0.89 那次「网关无声死亡」(仍敞着,见 memory)。
