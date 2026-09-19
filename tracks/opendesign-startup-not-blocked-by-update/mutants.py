"""变异红检:把实现逐个改坏,看判据咬不咬得住(track opendesign-startup-not-blocked-by-update)。

🔴 **只认失败行原文**。上一单栽过:第一版脚本 grep 的是段名,于是恒绿 —— 变异明明没被咬住
也报"咬住了"。这里逐个变异后必须在 unittest 的 FAIL/ERROR 行里**点名**到预期的判据。
"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

SRC = Path("bin/ds_update_startup.py")
PY_BIN = "/root/.venvs/design-studio/bin/python"

# (编号, 说明, 原文, 改成, 必须咬住的判据)
MUTANTS = [
    ("B1", "启动路径上偷偷查一次更新(最可能的假修复:只把超时改小)",
     "        if not isinstance(state, dict):",
     "        ds_update.check_for_update('0.0.1')\n        if not isinstance(state, dict):",
     "su_net3"),
    ("B2", "不再拒绝符号链接(安装包被换掉最省事的一条路)",
     "if os.path.islink(path) or not os.path.isfile(path):",
     "if not os.path.isfile(path):",
     "su12"),
    ("B3", "不校验 sha256",
     "        if h.hexdigest().lower() != want_sha.lower():",
     "        if False:",
     "su8"),
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
    ("B7", "轮询间隔去掉抖动(所有客户端同一秒打服务器)",
     "    delay = base * (1.0 + JITTER * (2.0 * r - 1.0))",
     "    delay = base",
     "sc2"),
    ("B8", "失败之后不退避",
     "    base = min(BASE_INTERVAL_S * (2 ** min(n, 16)), MAX_BACKOFF_S)",
     "    base = BASE_INTERVAL_S",
     "sc3"),
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
