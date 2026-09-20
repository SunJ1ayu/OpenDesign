"""变异红检:资格判据(`tests/test_ds_update_eligibility.py`)咬不咬得住。

**这份文件的来历**:它原来住在 `tracks/archive/opendesign-startup-not-blocked-by-update/`
里(那份归档原件一个字没动)。2026-09-20 track opendesign-update-duplicate-facts 把它搬到
`tests/` 与一堆 `mutation-*.sh` 做邻居 —— 理由很直白:**红检工具放在归档里,下次没人找得到**。
搬家**不代表它会被自动跑**;`tests/run-all.sh` 不跑这一批,它和所有 mutation-* 一样是手跑的。

用法:`python3 tests/mutation-update-eligibility.py`(在仓库根跑,它会原地改 `bin/` 再改回来)。
🔴 **它跑着的时候,这个仓库里不许跑任何别的判据或探针** —— 那一刻盘上的源码是被改坏的,
并发跑的东西读到的是变异版(2026-09-20 实测栽过一次:探针的 no_shell 场景回了 install,
因为当时 E4 正好把 no_shell 那一维拆掉了)。

和同目录 `mutants.py` 同一条纪律:**只认失败行原文** —— 变异之后必须在 unittest 的
FAIL/ERROR 行里**点名**到预期判据,光看 rc 会被"另一条题碰巧红了"骗过。

两处与 `mutants.py` 不同:
① 这套设计跨三个文件(`ds_auto_update` / `ds_update_startup` / `ds_web`),所以一个变异
   可以同时改几处 —— **纵深防线必须一起拆才问得出来**:只拆一层还绿不是漏网,是纵深在干活。
② `PYTHONDONTWRITEBYTECODE=1`:等长替换 + 同一秒 mtime 会让 CPython 复用旧 .pyc,
   既造得出假绿也造得出假红(2026-08-07 栽过)。
"""
import os, re, subprocess, sys
from pathlib import Path

PY_BIN = "/root/.venvs/design-studio/bin/python"
SUITE = "tests.test_ds_update_eligibility"
A, S, W = (Path("bin/ds_auto_update.py"), Path("bin/ds_update_startup.py"), Path("bin/ds_web.py"))

# (编号, 说明, [(文件, 原文, 改成), ...], 必须咬住的判据)
MUTANTS = [
    ("E1", "打开软件那一问不再查资格(界面照弹)",
     [(W, '                blocker = ds_auto_update.why_not_auto(paths, out.get("version"))',
          '                blocker = None')], "el10"),
    ("E2", "后台备货两层闸**一起**拆(单拆一层是纵深,拆不出来)",
     # 🔴 S 那一处的缩进 2026-09-20 变了:track opendesign-update-duplicate-facts 把
     #    `if paths is not None: ... elif ... else ...` 那三岔收成一行(判据 el17),
     #    于是原来 12 空格的锚点匹配 0 次。**变异本身一个字没变**,只对齐新代码。
     [(W, '        blocker = ds_auto_update.why_not_auto(paths, None)', '        blocker = None'),
      (S, '        blocker = ds_auto_update.why_not_auto(paths, facts["version"])',
          '        blocker = None')], "el11"),
    ("E3", "资格判据漏掉 disabled(业主把自动更新关了,照样弹、照样下)",
     [(A, '        if (os.environ.get("OPENDESIGN_AUTO_UPDATE") or "").strip().lower() == "off":\n            return "disabled"',
          '        pass')], "el10"),
    ("E4", "资格判据漏掉 no_shell(没外壳也说能装)",
     [(A, '        if re.fullmatch(r"[0-9]+", shell_port) is None:\n            return "no_shell"',
          '        pass')], "el10"),
    ("E5", "资格判据漏掉账本那一维(试过装不上的版本又弹一次)",
     [(A, '        if not auto_eligible(paths.get("data_root"), version):\n            return "attempted"',
          '        pass')], "el2"),
    ("E6", "永久否决里拿掉 attempted(该清的 46MB 不清)",
     [(A, 'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported")',
          'PERMANENT_BLOCKERS = ("not_installed", "path_unsupported")')], "el9"),
    ("E7", "永久否决里拿掉 path_unsupported(46MB 永远没人清 —— F4 那条)",
     [(A, 'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported")',
          'PERMANENT_BLOCKERS = ("attempted", "not_installed")')], "el14"),
    ("E8", "把**临时**否决也当永久(没外壳就把业主的包删了)",
     [(A, 'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported")',
          'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported", "no_shell", "disabled")')],
     "el15"),
    ("E8b", "**只**把 error 加进永久集(资格算不出来就把业主的包删了)",
     [(A, 'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported")',
          'PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported", "error")')],
     # el15 钉的是 no_shell/disabled 那两种临时条件,问不到 error 这一种 ——
     # 这正是本单 #28 要补的那个洞,咬住它的是为它新写的 el19。
     "el19"),
    ("E9", "apply 侧不再共用同一判据(F2 那条:自己再拼一遍,且漏了)",
     [(W, '        blocker = ds_auto_update.why_not_auto(paths, latest)', '        blocker = None')],
     "el4b"),
    ("E10", "apply 侧把「哪些否决是永久的」又自己写一遍(track opendesign-update-duplicate-facts #24)",
     [(W, '                if download is not None and auto.get("why_not") in ds_auto_update.PERMANENT_BLOCKERS:',
          '                if download is not None and auto.get("why_not") == "attempted":')],
     "el16"),
]


def run():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([PY_BIN, "-m", "unittest", SUITE],
                         capture_output=True, text=True, env=env)
    failed = set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out.stdout + out.stderr, re.M))
    return out.returncode, failed


def main():
    originals = {p: p.read_text(encoding="utf-8") for p in (A, S, W)}
    rc, failed = run()
    if rc != 0:
        print(f"🔴 未变异时判据就不是全绿({sorted(failed)}),先修好再来")
        return 1
    print("未变异:全绿 ✓\n")
    bad = 0
    try:
        for tag, why, edits, must in MUTANTS:
            ok = True
            for path, old, new in edits:
                if originals[path].count(old) != 1:
                    print(f"  [跳过] {tag} 锚点在 {path} 匹配 {originals[path].count(old)} 次 —— 脚本自己坏了")
                    ok = False
            if not ok:
                bad += 1
                continue
            for path, old, new in edits:
                path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
            rc, failed = run()
            hit = any(must in name for name in failed)
            caught = rc != 0 and hit
            bad += 0 if caught else 1
            print(f"  {'[咬住]' if caught else '[🔴 漏网]'} {tag} {why}")
            print(f"         期望 {must} 变红;实得 rc={rc} 红的有:{sorted(failed) or '无'}")
            for path, _old, _new in edits:
                path.write_text(originals[path], encoding="utf-8")
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")
    print(f"\n{'全部咬住' if bad == 0 else f'🔴 有 {bad} 条漏网'}")
    return 1 if bad else 0


sys.exit(main())
