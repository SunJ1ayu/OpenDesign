import os, sys, tempfile
BIN = "/root/.openclaw/workspace/projects/design-studio/bin"
sys.path.insert(0, BIN)
import ds_tools
root = tempfile.mkdtemp()
os.makedirs(os.path.join(root, "projects"))
p = os.path.join(root, "projects", "t.md")
open(p, "w", encoding="utf-8").write(
    "# t\n\n## 变更记录\n- [待确认] C1 2026-06-20 改推拉门\n\n"
    "## 变更历史\n- C1 备注:业主书面确认\n\n---\n最后更新: 2026-07-01\n")
before = open(p, encoding="utf-8").read()
r = ds_tools.edit_change("t", 1, ds_root=root)          # 什么字段都不给
print("空请求 ->", r)
print("文件逐字节不变:", open(p, encoding="utf-8").read() == before)
r2 = ds_tools.edit_change("t", 1, new_text="改推拉门", note="业主书面确认", ds_root=root)  # 同值
print("同值请求 ->", r2)
print("文件逐字节不变:", open(p, encoding="utf-8").read() == before)
