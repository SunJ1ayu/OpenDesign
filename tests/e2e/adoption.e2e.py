#!/usr/bin/env python3
"""T5 真链 e2e:散文件 → adopt_scan → stage_adoption → 人工 ds-approve → apply_plan → 落位。
纯 Python 核心 + 真起 ds-approve 子进程(人工闸)。断言真实文件移动。"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(REPO, "bin")
sys.path.insert(0, BIN)
import ds_adopt, ds_organize  # noqa

def w(base, rel, content=""):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)
    return p

fails = []
def chk(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond: fails.append(msg)

base = tempfile.mkdtemp(prefix="adopt-e2e-pkb-")
ws = tempfile.mkdtemp(prefix="adopt-e2e-ws-")
try:
    folder = "20260612 周宁 龙腾世纪 12#1802"
    for d in ("00-收件箱", f"01-项目/{folder}", "02-归档项目/2026", "03-共享资源/参考图库"):
        os.makedirs(os.path.join(ws, d))
    proj = os.path.join(ws, "01-项目", folder)
    # 项目根散文件:auto-project(pdf) / auto-workspace(jpg) / suggest(dwg) / 未知(xyz)
    w(proj, "户型量房单.pdf", "measure")
    w(proj, "业主收藏客厅.jpg", "img")
    w(proj, "施工平面.dwg", "cad")
    w(proj, "随手.xyz", "junk")
    w(base, f"projects/翡翠湾-1801.md", "# 翡翠湾-1801\n- 阶段: 方案深化\n")
    w(base, "config/workspace.json", json.dumps(
        {"root": ws, "projectsDir": "01-项目",
         "projects": {"翡翠湾-1801": f"01-项目/{folder}"}}, ensure_ascii=False))

    print("① adopt_scan 只读盘点")
    scan = ds_adopt.adopt_scan(base)
    bound = [p for p in scan.get("projects", []) if p.get("bound")]
    chk(any(p.get("key") == "翡翠湾-1801" for p in bound), "翡翠湾-1801 报告为已绑定")
    # 盘点是只读:文件一个没动
    chk(sorted(os.listdir(proj)) == sorted(["户型量房单.pdf","业主收藏客厅.jpg","施工平面.dwg","随手.xyz"]),
        "scan 后项目夹散文件原样未动")

    print("② stage_adoption 分流(auto→plan / suggest→advice / 未知→skipped)")
    st = ds_adopt.stage_adoption("翡翠湾-1801", ds_root=base, allowed_roots=[ws])
    chk(st.get("ok") is True, "stage 返回 ok")
    plan_id = st.get("plan_id")
    staged_names = {os.path.basename(o["src_rel"]) for o in st.get("staged", [])}
    chk(staged_names == {"户型量房单.pdf", "业主收藏客厅.jpg"}, "plan 只含 2 个 auto 文件(pdf+jpg)")
    chk([a["file"] for a in st.get("advice", [])] == ["施工平面.dwg"], "dwg → advice(不进 plan)")
    chk(st.get("skipped") == ["随手.xyz"], "未知扩展名 xyz → skipped")
    # stage 零写:apply 前文件仍在原处
    chk(os.path.exists(os.path.join(proj, "户型量房单.pdf")), "stage 阶段零移动(pdf 仍在项目根)")

    print("③ apply 未批准应被物理拒绝")
    pre = ds_organize.apply_plan(plan_id, allowed_roots=[ws], ds_root=base)
    chk(pre.get("error") == "not_approved", "未 ds-approve 时 apply 被拒(not_approved)")

    print("④ 人工 ds-approve(真起子进程,唯一造 .approved 的通道)")
    r = subprocess.run([sys.executable, os.path.join(BIN, "ds-approve"), plan_id],
                       env={**os.environ, "DS_ROOT": base}, capture_output=True, text=True)
    chk(r.returncode == 0, "ds-approve 退出 0")
    chk("已批准" in r.stdout, "ds-approve 打印批准回执")

    print("⑤ apply_plan 落位")
    ap = ds_organize.apply_plan(plan_id, allowed_roots=[ws], ds_root=base)
    chk(ap.get("ok") is True, "apply 返回 ok")
    chk(os.path.exists(os.path.join(proj, "01-资料", "户型量房单.pdf")), "pdf 落到项目内 01-资料/")
    chk(os.path.exists(os.path.join(ws, "03-共享资源/参考图库", "业主收藏客厅.jpg")),
        "jpg 落到工作区级 03-共享资源/参考图库/(workspace scope)")
    chk(not os.path.exists(os.path.join(proj, "户型量房单.pdf")), "pdf 原位已清空")
    chk(os.path.exists(os.path.join(proj, "施工平面.dwg")), "被引用 dwg 岿然不动(留在项目根)")
    chk(os.path.exists(os.path.join(proj, "随手.xyz")), "未知 xyz 未被碰")
finally:
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(ws, ignore_errors=True)

print(f"\n=== e2e: {'ALL PASS' if not fails else str(len(fails))+' FAIL'} ===")
sys.exit(1 if fails else 0)
