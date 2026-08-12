import os, sys, tempfile, shutil
sys.path.insert(0, "bin")
root = tempfile.mkdtemp(prefix="cnumprobe_")
os.makedirs(os.path.join(root, "projects"))
import ds_tools, ds_todo

DOC = """# 张三家
## 变更历史
- C03 备注:老备注
"""
BODY = """# 张三家

- [待确认] C3 2026-08-01 客厅刷白

## 变更历史
- C03 备注:老备注
"""

def fresh(body):
    p = os.path.join(root, "projects", "张三家.md")
    open(p, "w", encoding="utf-8").write(body)
    return p

def show(p, tag):
    txt = open(p, encoding="utf-8").read()
    print(f"--- {tag} 档案 ---")
    print(txt.strip())
    print("读侧 parse_history:", ds_todo.parse_history(txt))

# 场景 1:主变更行正常 C3,备注行手写成 C03,改备注
p = fresh(BODY)
r = ds_tools.edit_change("张三家", 3, note="新备注", ds_root=root)
print("场景1 改备注 →", r)
show(p, "场景1")

# 场景 2:同上,清空备注
p = fresh(BODY)
r = ds_tools.edit_change("张三家", 3, note="", ds_root=root)
print("\n场景2 清空备注 →", r)
show(p, "场景2")

# 场景 3:主变更行自己带前导零
BODY0 = BODY.replace("- [待确认] C3 ", "- [待确认] C03 ")
p = fresh(BODY0)
print("\n读侧看到的 cnum:", [c["cnum"] for c in
      (ds_todo.parse_change(l) for l in BODY0.split("\n")) if c])
r = ds_tools.edit_change("张三家", 3, new_status="已完成", ds_root=root)
print("场景3 改状态(cnum=3) →", r)
shutil.rmtree(root)
