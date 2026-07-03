# Design: opendesign-windows-prep

- Change: opendesign-windows-prep
- Status: final(无开放架构分叉——方向已经 主 agent 计划 + sub Claude 独立评审合并定稿,
  不跑 panel-explore;完整设计=计划 v2:`/root/aiwork/tasks/opendesign-next-step-plan.md`)

## Approach

四项 + 前置 sweep,只做不等用户输入的活:

0. **前置 sweep**:grep 全部工具脚本,三类清单——硬编码路径(`/root/`)、POSIX-only 调用、
   编码(`open()` 无 encoding / print 非 ASCII / `subprocess text=True` 无 encoding)。
   产出喂给①④。已知豁免:`ds_organize.py` 锁文件 `open(...,"a")`(无内容写入,无害)。
1. **ds-todo + list_todos**(唯一代码项):ds-todo(已是 Python)加 today 注入点
   (`DS_TODAY` env,默认行为不变);golden 特征化测试锁行为;`ds_tools.list_todos`
   改为 **import ds_todo 直调**(消灭 subprocess 编码面,顺带消灭"不查 returncode
   静默假成功"bug)。ds-todo 文件名无 `.py` 后缀 → import 用 importlib 按路径加载,
   或改名 `ds_todo.py` + 保留 `ds-todo` 为薄入口(倾向后者,名字更 Windows 友好)。
2. **skill 手册**:规范副本在 repo 内 `skills/organize/SKILL.md`、`skills/refs/SKILL.md`
   (nanobot workspace 只是部署目标,拷贝归部署步骤——避免双源漂移);AGENTS.md 两行瘦路由。
3. **deploy-security.md**:只方案不代码。key 归属/限额/撤销/用量可见性;**云上行边界**
   (业主对话必上 MiMo 云,与北极星"不上云"承诺的冲突,列为用户决策点);信任模型 =
   防模型越权、不防机主(措辞不用"绕过"攻击语汇);反向隐私(日志/备份不回传);
   用户决策点单独一节。
4. **Windows 启动物草稿**(全部标 UNTESTED):`bin/ds-nanobot.ps1`(key 注入按③,
   不照抄 auth.json——目标机没有 mimo CLI);config 模板占位符化(6 处 `/root/`);
   三工具 `DEFAULT_DS_ROOT` fallback 处理。依赖③。

## Key trade-offs / risks

- import 直调 ds_todo 替代 subprocess:少一个进程边界,ds_todo 崩溃会带着 MCP server 崩
  → list_todos 里 try/except 包住,错误显式返回 `{"error": ...}`(比静默假成功好)。
- ④只能静态走查,真验证等目标机——明确不声称完成,防"看起来做完了"的假绿。
- golden 测试锁的是**当前** Python 版行为(bash 版已不存在,无从对照)——若当前行为本身
  有 bug,golden 会把它冻住;写基线时人工过一遍输出合理性。

## Alternatives considered

- ds-todo bash→Python 重写:**前提过期**(7-02 已是 Python),任务不存在。
- subprocess + `encoding="utf-8"` + PYTHONUTF8=1 + 查 returncode:可行,但 import 直调
  一次性消灭整个编码面,更简。
- skill 文件直接写进 `~/.nanobot/workspace/skills/`:自造双源漂移 + 不进备份,否。

## Test strategy (oracle)

- ①:`tests/test_ds_todo.py` —— 固定 sample + `DS_TODAY` 注入 → golden 输出断言
  (含:有未关闭项、超期项目、全干净三种形态);`list_todos` 错误路径测试(坏 DS_ROOT →
  显式 error 非 ok:true)。既有 45 条(13+18+14)回归全绿。
- ②:机械化冒烟 —— import nanobot SkillsLoader,断言 organize/refs 进 skills summary
  (frontmatter 错则静默失效,人工看不出)。
- ③:文档审查项——决策点覆盖 F4 全部条目,无代码 diff。
- ④:静态走查 + sweep 清单闭环(④范围内修点清零);不跑真机。
- oracle 全部主 agent 写,submimo 如被委托,测试文件 off-limits。
