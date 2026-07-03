# Review task: opendesign-windows-prep(Windows 部署预备包)

你是独立代码评审员。仓库根 = 本文件所在目录的上两级(design-studio/)。
⚠️ 本仓库目录不在 git 追踪内,**没有 git diff 可看**;变更清单如下,请直接读文件评审。

## 本次变更(2026-07-03)

**代码(评审重点):**
1. `bin/ds_todo.py` — 新文件:主动提醒核心,`render(root, stale_days, today)` 返回字符串;
   `DS_TODAY` env 可冻结"今天";main() 里 stdout reconfigure(errors="replace")。
2. `bin/ds-todo` — 改为薄 CLI 入口(import 同目录 ds_todo)。
3. `bin/ds_tools.py` — `list_todos` 从 subprocess 拉起 ds-todo 改为 **import ds_todo 直调**,
   try/except 返回显式 `{"error": ...}`(修两个旧 bug:不查 returncode 静默假成功、
   subprocess 无 encoding 在 Windows cp936 下崩);顶部删 `import subprocess`、加 `import ds_todo`;
   `DEFAULT_DS_ROOT` 从硬编码 `/root/...` 改为基于 `__file__` 推导(bin/ 上一级)。
4. `bin/ds_organize.py` / `bin/ds_refs.py` — 同样的 `DEFAULT_DS_ROOT` 推导改法;
   ds_organize 另将 `DS_ORGANIZE_ROOTS` 分隔符从 `":"` 改为 `os.pathsep`。
5. `bin/ds-approve` — main() 开头对 stdout/stderr reconfigure(errors="replace")。
6. `tests/test_ds_todo.py` — 新 oracle:golden 三形态 + CLI 端到端 + list_todos 错误路径。
7. `tests/test_skills_smoke.py` — 用 nanobot SkillsLoader 断言 skills/ 可被加载。

**非代码(顺带看,不是重点):**
- `skills/organize/SKILL.md`、`skills/refs/SKILL.md`(给弱模型的用法手册;错误码表
  是否与 bin/ds_organize.py、bin/ds_refs.py 的真实 error 字符串一致,值得核)
- `bin/ds-nanobot.ps1`、`config/nanobot.config.windows.jsonc`(UNTESTED 草稿,做静态走查:
  语法/逻辑/路径是否自洽)

## 请评审

1. `ds_todo.render` 是否忠实复刻原行为?原实现是逐条 print(格式:两节,`▸ 名字`、
   `    行号:行内容`、空节打 `  (无)`,节间一个空行)。找 render 与 print 序列的语义差。
2. list_todos 直调的异常面:还有什么错误会溜成 `ok:true` 或把 MCP server 带崩?
3. `DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 有什么坑
   (symlink/打包/相对导入场景)?
4. os.pathsep 改动会不会破坏现有 Linux 行为?
5. 测试有没有假绿(尤其 golden 是否真的锁住了行为、monkeypatch 是否测到真路径)?
6. ps1/windows config 的静态错误(PowerShell 语法、env 展开时机、路径拼接)。

输出:findings 列表(严重度 + 文件:行 + 依据),最后一行给 PASS 或 BLOCK。
禁止改任何文件;测试文件与本 task 文件是 oracle,只读。
