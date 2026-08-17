# Design: opendesign-shell-chrome

## 一句话

**让外壳自己在地址里报身份**(`http://127.0.0.1:<port>/?shell=1`),前端读地址决定画不画
窗口栏 —— 地址在**第一帧**就在,和 pywebview 什么时候注入 API 完全无关。

## 三条路都摆出来,为什么选它

| 方案 | 首帧就对? | Linux 能判? | 代价 |
|---|---|---|---|
| A 听 `pywebviewready` 事件后再画(pywebview 官方推荐做法) | ❌ 晚一拍 | ❌ 一条都判不了 | 每次开窗口业主会看见界面**往下跳 30px** |
| B 外壳在地址里带标记(**选中**) | ✅ | ✅ 真 chromium 直接考 | 多一处跨语言字符串契约 |
| C A+B 都做 | ✅ | ✅ | 两个前提都要一直为真;A 那条只在 B 失效时才跑,而它跑的时候就是那一跳 |

**选 B。** 理由三条:

1. **首帧就对**。A 的注入发生在 `NavigationCompleted` 之后,那时页面早画完了 ——
   窗口栏一挂上去,`body` 的 `padding-top: 30px` 才生效,整个界面往下跳一格。
   08-17 四审(subdeepseek)专门为这一跳要求过 `useLayoutEffect`;A 会把那一跳请回来,
   而且是**每次开窗口**都跳。
2. **把"验不了"变成"验得了"**。这一层原来的说法是"要 pywebview,Linux 上一行都跑不了"。
   地址标记没有这个依赖:真 chromium 打开 `/?shell=1` 就该看见三个按钮 ——
   `tests/e2e/shell_chrome.e2e.mjs` 从此**每次总跑都在问这件事**。
   (这是本单最值钱的一半;修 bug 是另一半。)
3. **C 不是"更保险",是多一个要一直为真的前提**。外壳和前端装在同一个安装包里、
   同版本发出去,不存在"新前端配旧外壳";而"外壳忘了带标记"这件事由判据 x10
   机械地看着(它要求 `create_window` 那行引用常量,不许硬编码 URL)。

## 落到哪几行

1. `web/src/shellWindow.ts`
   - 新常量 `export const SHELL_MARK = "shell=1"` —— **前端这边唯一的字面量**。
   - `inDesktopShell(win)` 改为读 `win.location.search`,用 `URLSearchParams` 取
     `shell` 是不是 `1`(不做 `includes("shell=1")` 那种子串匹配:`?noshell=1`
     会假命中)。签名不变,仍然收一个可注入的 `win`,所以纯逻辑判据照样喂假对象。
   - 删掉 `pywebview` 那条依据,并把"为什么不能用它"的证据写在注释里(带源码行号)。
2. `bin/ds_shell.py`
   - 新常量 `SHELL_MARK = "shell=1"`(和上面一字不差,x10 对表)。
   - `create_window(APP, f"http://127.0.0.1:{web}/?{SHELL_MARK}", …)`。
3. `web/src/workspace/WindowChrome.tsx`
   - 只改注释里那句错话(「注入发生在页面加载那一刻」),逻辑一行不动:
     `useState(inDesktopShell)` 现在是**对的** —— 地址在首帧就定了,而且之后不会变
     (前端没有任何 `history.pushState/replaceState`,路由走 hash;外壳也从不 `load_url`)。

## 判据(oracle,主 agent 亲写,先单独 commit)

### 新增/改写

- `tests/test_shell_window.mjs`
  - **s-w1 改写**:地址里没标记 ⇒ false(浏览器里一个按钮都不许出现);
    `?shell=1` ⇒ true;`?shell=0` / `?shellx=1` / `?noshell=1` ⇒ false(子串匹配挡不住这三个)。
  - **s-w2 改写**:`{pywebview:{api:{}}}` 但地址没标记 ⇒ **false**。
    这一条就是本单的病根标本:旧判据在这里断言 true,把「API 注进来了」当成「我在外壳里」,
    而真机上那个条件在首帧永远不成立。**改判据的证据方向说清楚**:不是"它红了所以改",
    是 pywebview 5.4 源码证明这个问法在真运行时里问不出东西。
- `tests/test_shell_window_contract.py`
  - **x10 新增**:`ds_shell.SHELL_MARK` == `shellWindow.ts` 里的字面量,
    **且** `create_window(...)` 那段源码里的 URL 引用的是 `SHELL_MARK` 常量
    (硬编码一个 `?shell=1` 也能过第一半,所以要问第二半)。
  - **x4 补强**:窗口栏的分界不许再读 `window.pywebview`(那是"注入时机"这条老病的入口)。
- `tests/e2e/shell_chrome.e2e.mjs`(**新**,真 chromium + 真 ds_web,端口 8840)
  - **A 病本身**:`/?shell=1` ⇒ 三个按钮 `isVisible()`、`.win-bar` 在场、八个把手在场、
    `body` 的 `padding-top` 就是 30px。**修复前这一段必须是红的**(红检)。
  - **B 浏览器**:`/` ⇒ 三个按钮一个都不在、`body` 没有那 30px。
  - **C 命中测试(把 x8 的结构断言换成真浏览器里的行为)**:
    `elementFromPoint(关闭按钮中心)` 必须落在关闭按钮上;顶边 2px 处落在 `.win-grip-top`;
    顶边 15px 处落在 `.win-bar`(=拖动区真的点得到,不是被别的东西盖着)。
  - **D 拖动区不许被前端内容盖住**:`body.has-window-chrome` 之后,页面最上面那一排
    真正的界面元素不许伸进 0~30px 那一条(否则又是"看着有栏、按下去在点别的")。

### 保留不动

x1/x2/x3/x5/x6/x7/x8/x9、s-w7 —— 它们问的名字/层序/几何都还成立。

### 红检(对照组)

按 0.90.0 那条教训做:新判据先在 **HEAD(未修)** 上跑一遍 ——
e2e A/C/D 与 x10、s-w1/s-w2 必须红;修完再跑必须全绿。
"新判据红了"本身不算证据,要红在**这个**病上。

## 只有真机答得了的部分(仍然是真机清单)

- 三个按钮按下去动不动(最小化/最大化/还原/关闭进托盘);
- 拖那条栏、拖八条边,窗口跟不跟手、有没有吸附;
- 会话中途有没有黑窗口(0.90.0 的 B4,顺延到这一版一起看)。

## 版本

`ds-web 0.91.0` —— 安装器文件名和 `/api/health` 都取这个号,业主装完能自报是哪一版。
