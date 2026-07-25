# Design: opendesign-open-front-v2

- Change: opendesign-open-front-v2
- Status: draft

> 不是开放架构分叉:方向由 Windows 前台权规则唯一决定。不跑 panel-explore。

## Approach

**① 诚实的返回值**:`_win_activate` 从"调用过 SetForegroundWindow"改成**以
`GetForegroundWindow() == hwnd` 为准**回报成败;`_win_focus_folder` 据此返回。
0.44.0 把"调用过了"当成功,真机表现就是"说做了但没动静"。

**② 激活升级(两档)**:
- 温和档:`SW_RESTORE` + `SwitchToThisWindow`(alt-tab 用的那个)。够了就收手,不升级。
- 升级档:仍不在前台 → `AttachThreadInput` 把本线程输入队列绑到**当前前台窗口的线程**,
  借它的前台权做 `BringWindowToTop` + `SetForegroundWindow`,**finally 里必解绑**。
  这是 Windows 上的标准做法(不伪造按键、不改系统设置);不解绑会把两个线程的输入
  队列绑死,那才是真事故 —— 判据 a02/a03 专门锁这一点。

**③ 可诊断**:每次尝试落一行 `[open-front] …` 到 stderr(Windows 上 start.ps1 已把
stderr 重定向到 `%USERPROFILE%\.openDesign\logs\dsweb.err.log`)。三种结局各自可辨:
- `hwnd=… activate=True/False` —— 找到了窗口;给不给焦点看 activate;
- `no-match … seen=[标题…]` —— 压根没找到,**并把看到的资源管理器窗口标题列出来**;
- `error …` —— 枚举/激活抛了。

## Key trade-offs / risks

- `AttachThreadInput` 是"借前台权",比温和档更用力,但仍属文档化用法;真被系统或
  杀软拒绝时,返回 False 并落日志,行为退回今天的样子(任务栏闪),不倒退。
- **仍然证明不了真机效果** —— 判据全是假 user32。这一轮的价值一半在"更用力",
  另一半(可能更大)在"失败时能说出卡在哪"。
- 若日志显示 `no-match`,说明病根不是抢焦点而是**找不到窗口**(Win11 把文件夹开成
  标签页、标题模式不同),那时该换 COM 按真实路径匹配 —— 但那是下一轮,别现在猜。

## Alternatives considered

- **改系统前台锁定超时**(`SPI_SETFOREGROUNDLOCKTIMEOUT=0`):有效但**改的是用户的系统设置**,
  且要负责改回来。否。
- **伪造 Alt 按键骗过前台权**:经典脏招,杀软会盯。否。
- **直接上 COM 按路径匹配**:更准,但在不知道当前是"找不到"还是"抢不到"之前上,
  属于对着猜想写代码。等日志。

## Test strategy (oracle)

`tests/test_ds_web_open_front.py` 补两组(先红检,7 条):
1. `ActivateEscalation`:温和档够用时**不升级**(a01);不够用时升级且
   **AttachThreadInput 必须成对**、以解绑收尾(a02);系统就是不给焦点时返回 False
   且仍解绑(a03)。
2. `FocusDiagnostics`:命中要落 `hwnd=/activate=`(d01);未命中要落 `no-match` +
   **看见的窗口标题**(d02);异常要落 `error` 而不是静默(d03);
   `activator` 返回假时不得报成功(d04)。

**这个 oracle 能被什么骗过?**

- 老问题原样存在:所有断言都是"我的假 user32 被正确调用了",**真机会不会置顶依旧
  证明不了**。区别在于:这一版即使失败,日志也会告诉我们失败在哪一环 —— 判据 d02
  的"把看见的标题列出来"就是为下一轮准备的证据链。
- **假绿的具体形状**:a02 全绿但真机仍不置顶 = 系统拒绝借前台权(合法失败,日志会写
  `activate=False`);d02 全绿但真机日志空白 = ds_web 根本没更新(版本号回显那一闸接)。
