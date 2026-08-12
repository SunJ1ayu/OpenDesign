"""扫出 payload 里**只在 Windows 上才需要、但被漏掉**的依赖。

由来(2026-08-12 真机 S0 第一跑):`pip download --platform win_amd64` 只用平台标签挑
轮子,**环境标记(`sys_platform == 'win32'`)却是拿当前解释器判的** —— 在 Linux 上解析,
所有"仅 Windows 需要"的依赖被整批静默丢掉。业主机器上因此炸在
`No module named 'pywintypes'` / `'win32_setctime'`。

**不许只补眼前炸出来的那两个**(那是打地鼠):这里对着每个包的 METADATA 机械地扫,
把所有带 Windows 条件的必需依赖列出来,再比对包里有没有。

用法:win-deps-audit.py <site-packages 目录>    缺东西就退出码 1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WIN_HINT = re.compile(r"sys_platform\s*==\s*['\"]win32['\"]"
                      r"|platform_system\s*==\s*['\"]Windows['\"]"
                      r"|os_name\s*==\s*['\"]nt['\"]", re.I)
# extra == "..." 是可选附加功能,我们没装那些 extra,不该跟着要
EXTRA_HINT = re.compile(r"extra\s*==", re.I)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def dist_name(dirname: str) -> str:
    """`colorama-0.4.6.dist-info` → `colorama`。

    别图省事写 `rsplit('-', 1)[0]`:`.dist-info` 里**本身就带一个连字符**,
    那样切出来是 `colorama-0.4.6.dist`,于是"已装"集合全是坏名字、
    每个包都会被判成缺失 —— **一个永远红的闸和永远绿的闸一样没用**。
    (2026-08-12 我第一版就是这么写的,补完包之后它还在喊缺,才露馅。)
    """
    stem = dirname[: -len(".dist-info")] if dirname.endswith(".dist-info") else dirname
    return norm(stem.rsplit("-", 1)[0])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    sp = Path(argv[1])
    if not sp.is_dir():
        print(f"找不到目录:{sp}")
        return 2

    have: set[str] = set()
    for d in sp.glob("*.dist-info"):
        have.add(dist_name(d.name))

    needed: dict[str, list[str]] = {}
    for meta in sp.glob("*.dist-info/METADATA"):
        owner = dist_name(meta.parent.name)
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.lower().startswith("requires-dist:"):
                continue
            body = line.split(":", 1)[1].strip()
            if ";" not in body:
                continue
            req, _, marker = body.partition(";")
            if not WIN_HINT.search(marker) or EXTRA_HINT.search(marker):
                continue
            dep = norm(re.split(r"[\s<>=!~\[(]", req.strip(), 1)[0])
            needed.setdefault(dep, []).append(owner)

    missing = {d: who for d, who in sorted(needed.items()) if d not in have}

    print(f"扫了 {len(list(sp.glob('*.dist-info')))} 个包;"
          f"带 Windows 条件的必需依赖 {len(needed)} 个;缺 {len(missing)} 个")
    for d, who in sorted(needed.items()):
        mark = "缺!!" if d in missing else "在  "
        print(f"  [{mark}] {d}   <- {', '.join(sorted(set(who)))}")

    if missing:
        print("\n这些包只在 Windows 上才被要求,而 payload 是在 Linux 上解析的 ⇒ 被静默丢掉了。")
        print("补法:pip download --platform win_amd64 --only-binary=:all: " + " ".join(missing))
        return 1
    print("\n没有漏网的 Windows 条件依赖。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
