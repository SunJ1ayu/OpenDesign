# Tasks: opendesign-minimize-animation

- base-ref: bd9ca39de824911de5c8dd5ebfee91c3abb1987b

> 本单主 agent 自己干(`decision.json.execution_plan.adapter = main`)。
> 没派执行腿:改动十几行、判据全静态、且边界(不许碰非客户区)靠一条机械闸守着 ——
> 派出去的沟通成本比干活大。

## 调查(业主中途改口:「先不动手改」+「在 github 上找一些参考」)

- [x] 读 pywebview 的 WinForms 后端,确认 `frameless=True` 的实际动作
- [x] 把「无边框丢了什么」这一族列全(11 条,证据分三级)
- [x] 前提攻击:三个独立外部来源(Electron#751 / pywebview#1749,#1825 / VS Code#158065
      + 微软两处文档),摘录落盘 evidence/premise-attack-upstream.md
- [x] 给业主一份看得见的对照(artifact,含最小化动画的真实交互演示 + 三档做法)
- [x] 业主拍板:做方案 A

## 判据先行

- [x] 写 `tests/test_window_native_styles.py`(s1~s6),**红着先 commit** `e19f812`
- [x] s3 误报自查(它扫文本,把我注释里的名字当越界)→ 改用 ast 只问代码 `aced221`
- [x] 红检补 7 条变异 → 照出 s2/s5 两个洞(拿文本位置冒充代码结构)→ 补 `057439d`
- [x] 自审 F-G 逼出 s7(贴样式位不许拖累「缩小」本身)+ s6 改问可达性 `2359fae`

## 实现(方案 A,边界:只贴不影响绘制的位)

- [x] winuser.h 九个常量 + `_apply_native_styles`(读旧样式 → 或上三个位 →
      SetWindowPos FRAMECHANGED)`659ad0f`
- [x] `minimize()` 每次先确保一遍;窗口 `shown` 时也叫一次
- [x] A1:`show_window()` 先 `restore()` 再 `show()`
- [x] 自审修复:F-G 拆两层兜异常 / F-A `window_api` 进 `__init__` `70a320b`
- [x] bump 0.92.0 + 真机清单 0.92.0 `70a320b`

## 收口

- [x] 红检 18 条咬住 / 0 漏网(收下 panel 的 N8/N8b 之后是 20 条)
- [x] 最终收据(python 全量 1291/OK + mcp-gate + 红检 20/0)三份齐在 `656e606`
      —— 第一遍被断线砍成 rc=143,已在 setsid 下重跑;红过的那几遍逐份认账在 verify.md
- [x] panel-review(standard=1 腿;r1 subglm 被砍、r2 subkimi rc=1、r3 submimo 给了评审)
      逮到 restype 那条并已收下 `656e606`;主裁**代码面 PASS、产品面不给结论**
- [ ] 归档
- [ ] **业主真机走一趟 0.92.0 清单**(只有他答得了「按下去有没有动画」)

## 明确不做(留给方案 B,单独一单)

- [ ] B3 拖边缘分屏(要 `WS_THICKFRAME|WS_MAXIMIZEBOX`,会改非客户区)
- [ ] B4 Win11 Snap Layouts(要 `WM_NCHITTEST` 返回 `HTMAXBUTTON`)
- [ ] C1~C3 「假最大化」那一族(要真的用系统最大化 + `WM_NCCALCSIZE`)
