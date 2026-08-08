# Tasks: opendesign-owner-consent

- base-ref: `452a036`(开工时 HEAD = origin/main,ds-web 0.80.0)
- 状态:**只写了 proposal + design,一行代码没动。** 业主 08-08 傍晚出门,晚上继续。

## 👉 晚上从这里接(别靠摘要干活,先读 proposal.md 的"一条安全不变量已经过期")

- [ ] **T0 业主没答的那个问题**:这几天会不会让助手读**外面来的**文档(别人发来的
      合同/报价单)?**会 → 今晚先上止血版**(`set_workspace` 暂时直接拒绝,改工作区
      手工改配置),等正式开关做完再放开;**不会 → 按正常节奏一次做完,不折腾两次。**
      —— 这条是**业主拍板项**,别替他决定。
- [ ] T1 判据先行(主 agent 亲写,单独 commit):O1–O7,见 design.md。
      **O5 必须从工具表真相源枚举**,不许手抄危险工具清单(anydoc 那单栽过)。
      **O7 是本单最值钱的一条**:钉住「read_document 能读到的根 ⊆ 业主确认过的根」,
      让下一个扩读面的人当场红,而不是靠他记得回来看注释。
- [ ] T2 后端:`config/consent.json`(只由 ds_web 写,任何 MCP 工具都写不了)
      + `config/pending/<id>.json` + 一次性 + 照记录参数执行。
- [ ] T3 ds_web 新针孔(照抄针孔④ `_intake_approve` 的 posture:CT json 闸 → body 上限
      → 键白名单 → id 格式闸 → 后端判定)。**前端只带 id。**
- [ ] T4 ds-web 卡片 + 设置页两档开关(每次问我 / 不用问,默认问)。
- [ ] T5 修那条过期的安全论证(`ds_tools.py:805` 注释 + design.md B5),
      并把 O7 的闸指过去。
- [ ] T6 lane:full 四审 → 主裁 → bump 版本 → 归档。
- [ ] T7 真机:两台 Windows,重点看"卡片文案说得对不对"(影响面那句话)。

## 不做(已定)

- 不动 `ds_organize` 那条线(`.approved` 只有人在终端能造,比新机制强,替换=降级)。
- 不做"本次会话别再问这个工具"(先上两档,看它实际弹几次)。
