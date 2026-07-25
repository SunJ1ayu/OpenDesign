# Verify: opendesign-open-front-v2

- Date: 2026-07-25
- Verdict: **PASS(代码面)/ 真机待验**(ds-web 0.45.0)

## Mechanical checks(主 agent 亲跑)

- [x] `pytest tests/` 604 passed / 8 skipped(本单 oracle 26/26)
- [x] `npm run build` 绿(前端未改动,产物哈希不变)
- [x] 安全面零触碰:`_open_folder` 九道闸、`DS_OPEN_CMD` 分支、非 Windows 分支一字未动

## Review

- lane: **self**(主审自审)。理由:改动面 = 两个 Windows-only 函数的内部 +
  一行日志;不碰写路径/权限/钱/数据一致性,且**真正的判官是真机日志而不是评审意见**。
  上一单同一处已吃过 full 四审,本轮是对其 UNTESTED 结论的兑现动作。
- 规格自查:
  1. **这轮可能仍然不解决用户的问题** —— 若病根是"找不到窗口"(Win11 把文件夹开成
     标签页 / 标题模式不同),升级激活手段一点用没有。所以本轮真正的交付物是
     **那行诊断日志**;置顶升级只是顺手做的第二件事。这一点必须对用户说清楚,
     不能让他以为"这回肯定好了"。
  2. `AttachThreadInput` 是"借前台权",比温和档更用力。我判断它仍在文档化用法内
     (不伪造按键、不改系统设置),但**它确实比我上一单说的"不用抢焦点脏招"更进一步** ——
     属于我自己口径的松动,写在这里备查,用户若不接受可退回温和档。

### findings(自审)

1. **[已修·规格] 返回值语义**:0.44.0 的"成功"= 调用过 SetForegroundWindow,
   真机表现就是"说做了但没动静"。改成以 `GetForegroundWindow() == hwnd` 判定。
   连带旧判据 f01 的假激活器要显式返回真值(判据随规格走,已在 tasks 记录)。
2. **[已修·可诊断性]** 0.44.0 失败零日志 —— 这是本次真机排查卡住的直接原因,
   也是我上一轮的疏忽:一个"尽力而为、失败静默退化"的功能,**静默的是行为,不该是证据**。
3. **[风险·已锁判据] AttachThreadInput 必须成对**:不解绑会把两个线程的输入队列绑死。
   a02/a03 两条判据专门锁"以解绑收尾",且实现放在 `finally`。

## UNTESTED on target

- 仍然不能证明真机会置顶(判据全是假 user32)。**下一步的判官是
  `%USERPROFILE%\.openDesign\logs\dsweb.err.log` 里的 `[open-front]` 行**:
  - `activate=False` → 找到了窗口但系统拒绝给焦点 ⇒ 退路是前端提示"已在任务栏打开";
  - `no-match seen=[…]` → 根本没找到窗口 ⇒ 下一轮改用 COM(Shell.Application)按真实
    路径匹配,而不是按标题;
  - 日志里**什么都没有** → ds_web 没更新到 0.45.0(先核版本号回显)。

## Accepted deviations

- 升级到 `AttachThreadInput`(见规格自查 2)。
- 未做 COM 路径匹配:在不知道是"找不到"还是"抢不到"之前做,等于对着猜想写代码。
