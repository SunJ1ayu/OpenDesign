# Tasks: opendesign-due-writer

- base-ref: `ae2d1035ffe67789cc226c09db3e048a59ac8dff`(ds-web 0.69.0)

## 做

- [x] **判据先行**:`tests/evals/due_writer_eval.py` —— 真跑工具循环、读档案断言 `⏳`
      (主 agent 亲自写)。**先红检**:1 FAIL / 6,红在"一批三条"那题(见 verify.md)
- [ ] A `set_due_date_tool` / `append_change_tool` 的 docstring:从功能描述改成职责描述
      (什么时候主动设、相对期限自己按 `Current Time` 算、**没给期限不许编**、
      **一批里带期限的那条记完立刻补**)
- [ ] B `workspace/AGENTS.md`:工具表补 `set_due_date` 一行;操作契约加"期限也要记"一条
- [ ] C `bin/start.ps1`:启动时幂等同步 `workspace\AGENTS.md`+`SOUL.md`+`skills\*`
      到 `%USERPROFILE%\.nanobot\workspace`(补上"改了契约不重装就到不了真机"的洞),
      失败只警告不阻断启动,并打印一行"已同步助手契约"
- [ ] 收货:考卷**连跑两遍**都绿(模型有方差,一遍不算)+ resolver_eval 不退化
      + pytest/mjs/build 回归
- [ ] verify.md 落 findings 与主裁

## 👉 接下来给用户的话(别忘了说)

1. **0.69.0 已 push**(`ae2d103`),装机口径见 [[opendesign-deploy-paths]];
   两条要他亲眼看的在 `tracks/opendesign-todo-one-view/tasks.md`(软轨方向、批次小标题重复)。
2. **本单交付后必须重装、或至少让新版 start.ps1 跑一次**,否则 AGENTS.md 那半到不了
   真机 —— 装完看那行"已同步助手契约"。**盘上和运行时对不上 = BLOCK,不是警告。**

## 真机待验(考卷接不住的,只能等他用几天)

- [ ] **硬轨里到底有没有东西**:用他自己的微信原文喂几天,待办页"有截止日"那一轨
      不再恒空 —— 这才是本单成不成的唯一判据,考卷全绿也代替不了。
- [ ] **抽查一条硬轨的日期**:是不是业主真说过的那天(防模型编日期)。
- [ ] 如果**一批多条时仍然掉截止日** → 按 design.md 预先写死的升档规则,
      起第二单给 `append_change` 加 `due` 参数,**lane full**,不在本单调措辞凑绿。

## 下一单(顺序照旧,别跳)

**④ 阶段计时器**(用户 08-01 自己提的):每个项目在当前阶段待了几天 + 总天数。
⚠️ 数据完全不存在 —— `ds_tools.set_stage` 只替换头部 `- 阶段:` 一行 + 刷页脚,
**阶段变更日期一个字都没存** ⇒ 动档案格式 = 新写面 ⇒ **单独起 track,lane full**。
