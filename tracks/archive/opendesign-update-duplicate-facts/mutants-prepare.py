"""变异红检(prepare/startup 卷)——**本单的工作副本**,track opendesign-update-duplicate-facts。

来历:`tracks/archive/opendesign-startup-not-blocked-by-update/mutants.py`。归档那份**一个字都没动**
(归档是历史收据,改它 = 篡改)。本单要用它做一件归档版做不了的事:**同一套变异,在我重写
pr 卷夹具之前跑一遍、之后再跑一遍,逐条比红绿**(design.md 的 oracle T6)。

🔴 直接跑归档那份的读数:**12 条咬住、4 条锚点失效**(B1 匹配 2 次,B3/B7/B8 匹配 0 次)。
拿一份 25% 的子弹是哑弹的枪去证明"我没把判据改松",证据力不够。所以这份副本修了锚点:

  B1  锚点 `if not isinstance(state, dict):` 现在在文件里出现 **2 次**
      (`startup_decision` 与 `_sweep_installed` 各一处)⇒ 加上下文钉死前者。**变异本身不变。**
  B3  「不校验 sha256」打的是**启动路径**上那次哈希。su15 之后启动侧不再算哈希
      (判据自己写着"su8 搬走了,不是删"),prepare 侧的同一件事由 B11/B16 咬 ⇒ **这条已过期,删**。
  B7  「轮询间隔去掉抖动」/ B8「失败之后不退避」:后台轮询调度器
      (`JITTER` / `BASE_INTERVAL_S` / `next_delay` 配 sc1~sc4)2026-09-20 整段删掉
      —— `grep -rn JITTER bin/` 现在 0 命中 ⇒ **这两条打的是不存在的代码,删**。

删掉三条是**减少**报警器,所以理由必须是机械可查的:被变异的代码不存在了(上面每条都给了
查法),不是"它本来就弱"。删之前与删之后都不动任何一条判据。


🔴 **只认失败行原文**(继承归档那份的纪律):变异之后必须在 unittest 的 FAIL/ERROR 行里
**点名**到预期判据,光看 rc 会被"另一条题碰巧红了"骗过。
"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

SRC = Path("bin/ds_update_startup.py")
PY_BIN = "/root/.venvs/design-studio/bin/python"

# (编号, 说明, 原文, 改成, 必须咬住的判据)
MUTANTS = [
    ("B1", "启动路径上偷偷查一次更新(最可能的假修复:只把超时改小)",
     # 锚点带上下一行 `return _enter("no_state")`:光凭第一行在本文件里有 2 处
     # (startup_decision 与 _sweep_installed),会被判成"脚本自己坏了"。
     "        if not isinstance(state, dict):\n            return _enter(\"no_state\")",
     "        ds_update.check_for_update('0.0.1')\n        if not isinstance(state, dict):\n            return _enter(\"no_state\")",
     "su_net3"),
    ("B2", "不再拒绝符号链接(安装包被换掉最省事的一条路)",
     "if os.path.islink(path) or not os.path.isfile(path):",
     "if not os.path.isfile(path):",
     "su12"),
    ("B4", "不校验字节数",
     "        if os.path.getsize(path) != want_size:",
     "        if False:",
     "su9"),
    ("B5", "去掉兜底 try —— 坏状态直接抛(= 软件打不开)",
     "    except Exception:  # noqa: BLE001 —— 判据 su13:宁可不更新,绝不许打不开\n        return _enter(\"decision_failed\")",
     "    except ZeroDivisionError:\n        return _enter(\"decision_failed\")",
     "su13"),
    ("B6", "write_state 不走 os.replace(留下半写窗口)",
     "        os.replace(tmp, str(p))",
     "        shutil.copyfile(tmp, str(p)); os.unlink(tmp)",
     "sw2"),
    ("B9", "不认 schema(将来换格式时会拿旧状态去装)",
     "        if state.get(\"schema\") != SCHEMA:",
     "        if False:",
     "su5"),
    ("B10", "版本判断写成 < 而不是 <=(同一版会被重装一次)",
     "        if target <= current:",
     "        if target < current:",
     "su10"),
    ("B11", "prepare 不校验下载回来的摘要",
     "        if ds_update_apply.sha256_file(dest).lower() != facts[\"sha256\"].lower():",
     "        if False:",
     "pr3"),
    ("B12", "prepare 动手前不写 downloading(断电后下次启动会看到假的 ready)",
     "        write_state(state_file, {\"schema\": SCHEMA, \"phase\": \"downloading\",",
     "        _skip = ({\"schema\": SCHEMA, \"phase\": \"downloading\",",
     "pr5"),
    ("B13", "校验失败后不删坏包",
     "        if os.path.isfile(dest):\n            os.unlink(dest)",
     "        pass",
     "pr3"),
    ("B14", "同一版重复下载(白烧业主流量)",
     "        if (isinstance(current, dict) and current.get(\"phase\") == \"ready\"",
     "        if (False and isinstance(current, dict) and current.get(\"phase\") == \"ready\"",
     "pr7"),
    ("B15", "prepare 去掉兜底 —— 后台任务能把主进程搞崩",
     "    except Exception:  # noqa: BLE001 —— 判据 pr6\n        return {\"ok\": False, \"reason\": \"prepare_failed\"}",
     "    except ZeroDivisionError:\n        return {\"ok\": False, \"reason\": \"prepare_failed\"}",
     "pr6"),
    ("B16", "prepare 不校验字节数",
     "        if not os.path.isfile(dest) or os.path.getsize(dest) != facts[\"size\"]:",
     "        if False:",
     "pr4"),
]


def run():
    out = subprocess.run([PY_BIN, "-m", "unittest", "tests.test_ds_update_startup"],
                         capture_output=True, text=True)
    failed = set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out.stdout + out.stderr, re.M))
    return out.returncode, failed


def main():
    original = SRC.read_text(encoding="utf-8")
    rc, failed = run()
    if rc != 0:
        print(f"🔴 未变异时判据就不是全绿({len(failed)} 条红),先修好再来")
        return 1
    print(f"未变异:{len(failed)} 条红 ⇒ 全绿 ✓\n")
    bad = 0
    try:
        for tag, why, old, new, must in MUTANTS:
            if original.count(old) != 1:
                print(f"  [跳过] {tag} 锚点匹配 {original.count(old)} 次 —— 脚本自己坏了")
                bad += 1
                continue
            SRC.write_text(original.replace(old, new, 1), encoding="utf-8")
            rc, failed = run()
            hit = any(must in name for name in failed)
            mark = "[咬住]" if (rc != 0 and hit) else "[🔴 漏网]"
            if not (rc != 0 and hit):
                bad += 1
            print(f"  {mark} {tag} {why}")
            print(f"         期望 {must} 变红;实得 rc={rc} 红的有:{sorted(failed) or '无'}")
    finally:
        SRC.write_text(original, encoding="utf-8")
    print(f"\n{'全部咬住' if bad == 0 else f'🔴 有 {bad} 条漏网'}")
    return 1 if bad else 0


sys.exit(main())
