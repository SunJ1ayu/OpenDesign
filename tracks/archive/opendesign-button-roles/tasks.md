# Tasks: opendesign-button-roles

- base-ref: cd3047c523396add08c4fa80879f1d04916edbd8(0.66.0)
- 状态:**DONE,交付 0.67.0**(执行腿 codex `gpt-5.5`,2 轮,自身实现错误 0 处)

> 委托规矩:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现交给它;
> oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 👉 从这里接

**这一单的第二目的**:给 [[model-tiering-trial]] 补一个 **GPT 档返工率样本**。
07-27 换档到 codex 时样本只有 1 单,记了「⏳ 欠三单返工率记账」,到 07-31 一单没记 ——
因为 0.63→0.66 四单我都自己干了(根因见记忆 `self-narrated-fields-dont-guard`)。
**收货时必须记账**:返工几轮、我事后改了多少、判据抓到什么、评审腿抓到什么。

## 判据(主 agent 亲写,执行腿逐字节 off-limits)

- `tests/test_button_roles.mjs` —— 静态总覆盖,**3 条红**
- `tests/e2e/button_roles.e2e.mjs` —— 行为 + 观感,**10 条红**

## 待做

- [x] **T1 九个使用点换成角色 class + 删三条 CSS 规则** —— 已派 codex `gpt-5.5`,
      清单见 design.md 的表。
- [x] **T2 收货三闸**:① oracle 逐字节 diff 必须为空 ② 主 agent 亲跑判据 + 全量回归 + build
      ③ 亲读 diff(含盯 `create mode 120000`)
- [x] **T3 截图** —— **必须截到聊天区与整理方案两处**。判据只钉一致性,钉不住
      "整体更难看",而那两处正是最可能变难看、又最难截到的。
- [x] **T4 fast lane 评审**(主审 + 1 腿)
- [x] **T5 merge + bump 版本 + push + 归档**;真机待验清单加一条
- [x] **T6 返工率记账**(本单的第二目的,别忘)

## 真机验收要问用户的一句话

**「按钮统一成这样够不够,还是你其实想换个样子?」**
proposal 里记了这层转译风险:他说的是"丑 / 统一一下",我翻译成"收编到现有三档"。
**判据对这个永远是绿的。**
