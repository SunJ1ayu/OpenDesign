# Tasks: opendesign-native-frame

base-ref: eead395

## 0. 开工前必须先过的闸

- [x] **P0 探针(FAIL,见 evidence/p0-result.md):pythonnet 能不能覆写 `WndProc(ref Message m)`**
      —— design.md 未知 #1。**探针没绿之前不许写实现。**
      这一步需要一台 Windows;Linux 上无解。
- [x] **P1 探针 PASS(evidence/p1-result.md):改用 ctypes `SetWindowLongPtrW(GWLP_WNDPROC)` 经典子类化、绕开 pythonnet ⇒ 未知 #1 定案,方案 B 可行**
- [x] `track-record validate --phase dispatch`(**当前被权限拦住,欠**)
- [x] 双出:**没花 panel-explore**。P0/P1 两轮真机探针把最大的分叉(pythonnet 还是 ctypes)
      直接定案了 —— 那比任何模型意见都硬。premise attack 三份一手证据已落盘。

## 1. 判据先行(单独 commit,先红后绿)

- [x] s1 样式位常量对表 winuser.h(新增 `WS_CAPTION` / `WS_THICKFRAME`)
- [x] s2 `needed` 必须同时含 CAPTION + THICKFRAME;**去掉任一位必须红**
      (这条钉死 0.92 的错误规格,防止有人为"外观安全"又砍回去)
- [x] s3 `WM_NCCALCSIZE` 分支区分 wParam 真假,真分支改 rgrc 且置 Result=0
- [x] s4 新增 ctypes 调用点 argtypes **和** restype 都声明(继承既有判据)
- [x] s5 `show_window()` 不许对最大化窗口无条件 restore(D3 连带)
- [x] s6 结构闸:加了 CAPTION 就必须存在 NCCALCSIZE 处理(防中间态发版)
- [x] 红检:每条判据都要有能咬动它的变异

## 2. 实现(顺序不能换)

- [x] D1 样式位扩到五个(**不许单独发版**)
- [x] D2 `NativeWindow` 子类化 + `WM_NCCALCSIZE`(含最大化客户区修正)
- [x] D2b 日志:第一次真收到 NC 消息时打一行,不是挂载时打
- [x] D3 拆假最大化 → `WindowState.Maximized`;同步改 `_is_max` 与 `show_window()`
- [ ] D5 圆角/阴影不劣化(未知 #2)—— **代码没碰,留真机 C4 观察**
- [ ] D4 **真机确认系统拖拽正常之后**,再删自绘的 resize 热区(单独 commit)

## 3. 收口

- [x] 全量回归(用 venv 解释器,不是系统 python3)
- [x] 四审 panel-review(impact=standard ⇒ 预算 1,可加证据不可减)
- [x] bump 版本 + 打安装包 + 成品闸
- [ ] **真机清单:两台机器都要走**(公司 F: 那台若是 Win10,`wParam==0` 那条分支
      在 22000 以下要另处理 —— WinFormedge 专门打过补丁)

## 明确不做(继承 proposal 的 non-goals)

- 自绘动画、等 pywebview 7.0、改前端按钮外观、给 pywebview 提 PR


## 收口状态(2026-08-23 深夜)

- **代码面主裁 PASS**;产品面不给结论(证据边界,见 verify.md)。
- 安装包已打:`/root/aiwork/out/opendesign-0.93.0/OpenDesign-Setup-0.93.0.exe`
  (59.8 MB,7 条成品闸 0 不合格;安装包里的 ds_shell.py 与仓库逐字节一致)。
- 已 push(远端 `1d9680a` 回读确认);已发 pre-release `win-installer-0.93.0`
  (远端 digest 与本地 sha256 逐字节一致)。
- **暂不归档,等真机**。0.92 就是归档之后被真机证伪、只好另开一单;
  这次把 track 挂着,真机绿了再归档,红了直接在这一单里接着修。

## 🔴 真机结果(2026-08-24):FAIL —— 打开就是全白

业主原话:「opendesign项目我验收了,打开全是白的什么都没有了」。

### 我在本地核实过的(事实,不是推断)

1. **他装的确实是 0.93.0**:release `win-installer-0.93.0` 的 downloadCount 由 0 变 1;
   发布物 digest `sha256:adb103f4…` 与本地 `out/opendesign-0.93.0/OpenDesign-Setup-0.93.0.exe`
   逐字节一致 ⇒ 我在本地拆的就是他机器上跑的那一份。
2. **包里的前端产物完好**:`pkg/ds/web/dist/index.html` 引用的
   `/assets/index-nULi_wUm.js` 与 `/assets/index-DrDJWOTn.css` **都在包里**,
   与仓库 `web/dist/` 一致 ⇒ 白屏**不是**资源缺失/产物打错。
3. **0.92 与 0.93 的前端逐字节相同**:`diff -rq` 两个 pkg 的 `ds/web/dist` 无差异。
   而 0.92 他跑过、界面看得见(当时反馈的是「动画还是没有」)。
4. **`ds_web.py` 在 0.92→0.93 之间只改了 VERSION 字符串与注释**(12 增 1 删,全是注释)。

⇒ **「能看见界面」到「全白」之间,唯一的功能性差量是 `bin/ds_shell.py` 的方案 B**
(WS_CAPTION|WS_THICKFRAME + 接管 `WM_NCCALCSIZE` + 真最大化),
且它挂在 `shown` 上(`ensure_native_styles`)⇒ **开窗口就跑**,与「打开就白」时间点吻合。

### 还不知道的(**别写成事实**)

- 白的是**外壳窗口没画出内容**,还是**网页本身没起来**。两者现场长得一样。
  分界靠业主两件事:①`外壳.log` ②在浏览器里开 `http://127.0.0.1:8766/` 看有没有界面。
- 具体机制(客户区算错 / WebView2 子窗口没跟着重排 / 首帧被 SWP_FRAMECHANGED 打断)
  **一条都还没有证据**,不许挑一个写进结论。

### 判据的洞(和 0.91 同一个形状)

这一单的判据全绿、四审 PASS,**但没有一条问过「页面还画不画得出来」**。
0.91 那次是「12 条判据全绿却没一条问过窗口栏会不会被画出来」—— 同一种病:
**判据把"样式位贴对了没有 / 消息接管了没有"当成了目标,而业主要的是"看得见"。**
修复这一单时,判据必须先补上这一条(而且要能在 Linux 上问得出来才有意义)。

### 为什么评审没拦住(业主 08-24 追问,逐条核实过才写)

**先纠正一个前提:那轮不是四审,是两审。** 花名册(verify.md)白纸黑字:
subglm 的 agent 腿跑满 900s 超时、回落 chat 腿连撞 HTTP 503,两段都没产出;
subkimi 是 `no credential configured`。**成功两条**(mimo / deepseek)。
但这**不是主因** —— 四条腿一样查不出来,理由见下。

**更要紧的是:主裁当时并没有说界面没问题。** verify.md 的 verdict 原文是
**「代码面 PASS。产品面不给结论。」**,而且专门写了:
「这一版的风险高于 0.92……失败形态是**外观当场坏掉**(多一条线 / 冒出标题栏 / 内容被挤)」。
subdeepseek F4 也明确标了「核心前提未验」。

⇒ **所以这不是"漏判",是"它答不了,而我知道它答不了,包照发"。**

三条实打实的原因:

1. **没有任何一条腿、任何一条判据能在 Windows 上把窗口画出来。** 全部机器证据回答的
   都是"手段有没有写错"(AST 读源码)。**这一层早有前科**:同一单的 F-A ——
   `ensure_native_styles` 指着改名前的函数,窗口一 `shown` 就 AttributeError ——
   **10 条判据 + 1299 项回归全都没咬住**,是我自己肉眼看出来的。
   同一个盲区在同一单里已经现过形,我没把它的份量看够。
2. **腿只验"合不合规格",而规格是我写的。** 我的规格问的是"样式位贴对没有 /
   消息接管生效没有",不是"页面还看得见吗"。规格错的时候 panel 验不出来 ——
   0.92 已经这样死过一次,这次换了个地方同病。

3. 🔴 **真机清单本身犯了同一个病(这条是本次新查出来的)。**
   - C 组五条全在问**退化**:多一条线 / 冒出真标题栏 / 内容被挤掉一点 / 圆角阴影 /
     盖住任务栏。**没有一条问「界面还在不在」。**「整个客户区一片白」
     从这五条中间**直接漏过去**:它不是多一条线,不是冒标题栏,也不是"挤掉一点"。
   - A 组那道硬闸(「不过这两条,后面全不作数」)是 A1 翻日志找一行字、
     A2 看记事本的动画。**业主打开就是一片白,而清单让他第一步去搜日志文件。**

⇒ 修法不是"多加一条评审腿"(腿再多也读不了屏幕)。是把**最粗的那个问题放到最前面**:
**任何真机清单的第一条永远是「打开,界面正常出来了吗?不正常就停,别往下走」。**
判据侧同理:这一单的判据补强必须先能问出"页面还画不画得出来",再谈样式位。
