"""判据用的临时目录登记表 —— 建的时候登个记,进程退出时统一收。

存在的理由(2026-08-17):业主报「磁盘满了」。50G 盘 94%,`/tmp` 里 205,666 个条目
几乎全是本仓库判据 `mkdtemp` 出来又没人收的空壳目录,跑一轮总跑新增约 1.7 万个。

── 为什么不用仓库里现成的 `self.addCleanup(shutil.rmtree, ...)` ──────────────
本仓库有 60 处调用点是那么写的,收得干干净净,那个写法没问题 —— 但它够不着这 44 处。
两个原因,第二个是硬的:

① **拿不到 `self`。** 漏的这 44 处全在**模块级辅助函数**里(`_mkroot()` / `_mkdist()`
   这种,被几十条用例调用,有的还是 `_serve(_mkroot({}))` 这样内联传进去、
   连个变量都没接)。模块级函数手上没有 `self`,写不了 `addCleanup` ——
   **这正是它们当初漏掉的原因**,不是谁偷懒。

② **`addCleanup` 会缩短目录的存活期。** 它在**每条用例结束**时收;而这些目录
   现在的存活期是"整个模块跑完(其实是永远)"。把存活期从"模块"缩到"用例",
   是在**改判据的隔离语义** —— 万一某条判据靠目录跨用例传状态,它会变成绿的、
   但测的东西少了。那种坏最难发现,也正是本机最忌讳的"改考卷让自己及格"
   (哪怕不是故意的)。

`atexit` 让目录活到**进程退出**为止 ⇒ 判据跑动期间的行为**逐字节不变**,
只是散场时把椅子摆回去。这是能修掉泄漏的改动里,行为改动最小的一种。

── 边界 ──────────────────────────────────────────────────────────────────
- 进程被 SIGKILL 打死时 `atexit` 不跑,会留下这一轮的目录。这是**可接受的残渣**:
  实测干净判据在 `/tmp` 里也各有 1 个,就是历次跑崩留下的,不累积。
- 收的时候一律 `ignore_errors=True`:清理失败不许把判据的结论带红 ——
  **量具不许污染被测物**。

用法(替换掉 `tempfile.mkdtemp(prefix=X)`):

    from . import _tmpreg          # 或 import _tmpreg,随该文件现有风格
    d = _tmpreg.mkdtemp("ds_web_api_")

守它的闸:`tests/tmpdir-leak-gate.sh`(把判据跑在空台面上,跑完必须剩 0)。
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

# 登记过的路径(目录或文件),按登记顺序。只增不删 —— 散场时一把收。
_DIRS: list[str] = []


def mkdtemp(prefix: str) -> str:
    """和 `tempfile.mkdtemp(prefix=...)` 行为一致,额外把目录登记下来。"""
    d = tempfile.mkdtemp(prefix=prefix)
    _DIRS.append(d)
    return d


def register(path: str) -> str:
    """登记一个**不是 mkdtemp 建的**路径(文件或目录),原样返回,方便内联。

    为什么需要它:`test_ds_web.py` 的逃逸判据要在临时目录**隔壁**放一个诱饵**文件**
    (`secret-<名字>`),证明服务端不会顺着 `..` 读出去。那个文件直接落在 TMPDIR 上,
    既不是 mkdtemp 建的、也不在任何临时目录里面 ⇒ 收目录收不到它,普查按 `mkdtemp`
    找也找不到它 —— 清理前 `/tmp` 里堆了 **3766 个**。
    它是被泄漏闸自己抓出来的,不是我数代码数出来的:**行为闸看得见静态扫描看不见的东西**。
    """
    _DIRS.append(path)
    return path


@atexit.register
def _sweep() -> None:
    """进程退出时统一收。失败不吭声 —— 清理不该改变判据的结论。"""
    while _DIRS:
        p = _DIRS.pop()
        shutil.rmtree(p, ignore_errors=True)      # 目录
        try:
            os.remove(p)                          # 文件(rmtree 对文件不管用)
        except OSError:
            pass
