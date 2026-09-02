"""两份同时启动时,让位方向唯一 vs 整段都问 —— 到底活下来几份。

为什么有这支探针(2026-09-02):`bin/ds_shell_core.py` 的 `_someone_ahead_of` 里写着
"改成整段都问是不行的,我量过:两份同时启动时会双向让位,3 轮里有 1 轮存活 0 份"。
第二轮评审的两条腿(subdeepseek 与被砍前的 subkimi)**各自独立**指出:
这个数是驳回"唯一能堵住拓扑盲区的便宜修法"的**全部依据**,而仓库里没有它的探针、
没有收据、没有对照组 —— 正是这一单自己刚给 connect_latency 补掉的那个形态
("量出来的数活在文档里,仓库里复现不出来")。所以补这一支。

它量什么:两份实例**同时**跑 `acquire()`,数最后有几份认为自己是唯一的(=活下来几份)。
  A 组 = 树上的实现:`_someone_ahead_of` 只问 `p < mine`(让位方向唯一)
  B 组 = 评审建议的改法:绑完之后问**整段**(除了自己),两个方向都问

判读:
  A 组必须**恒等于 1**。出现 0 或 2 都是这把锁的严重缺陷。
  B 组只要出现过 0,"整段都问"这条修法就被证伪 —— 业主双击之后一个窗口都不开。

⚠️ 它模的是什么、不是什么:同一个进程里的两个线程、Linux 回环。真实场景是业主那台
   Windows 上的两个进程。**竞争窗口的绝对宽度会不一样**,所以这里的比例别当成
   业主那台机器上的概率;能被它证伪的是"B 组结构上会不会出现 0 存活"这件事本身。
"""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "bin"))
import ds_shell_core as core  # noqa: E402


def free_base(span: int) -> int:
    """找一段连续空着的锁位。"""
    while True:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        base = s.getsockname()[1]
        s.close()
        probes = []
        try:
            for p in range(base, base + span + 1):
                q = socket.socket()
                q.bind(("127.0.0.1", p))
                probes.append(q)
        except OSError:
            continue
        finally:
            for q in probes:
                q.close()
        return base


def ask_whole_range(self, mine: int) -> bool:
    """B 组:绑完之后问整段(除了自己)—— 评审建议的修法。"""
    return self._scan((p for p in self._ports() if p != mine), patient=True) is not None


def one_round(base: int, span: int) -> int:
    """两份同时 acquire(),返回活下来几份。"""
    ready = threading.Barrier(2)
    locks = [core.InstanceLock(base_port=base, span=span) for _ in range(2)]
    got = [None, None]

    def run(i):
        ready.wait()
        got[i] = locks[i].acquire()

    threads = [threading.Thread(target=run, args=(i,)) for i in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    try:
        return sum(1 for g in got if g is True)
    finally:
        for lk in locks:
            try:
                lk.release()
            except Exception:
                pass


def measure(label: str, rounds: int, span: int, patch: bool) -> dict:
    original = core.InstanceLock._someone_ahead_of
    if patch:
        core.InstanceLock._someone_ahead_of = ask_whole_range
    try:
        tally = {0: 0, 1: 0, 2: 0}
        for _ in range(rounds):
            tally[one_round(free_base(span), span)] += 1
    finally:
        core.InstanceLock._someone_ahead_of = original
    print(f"{label}")
    for k in (0, 1, 2):
        print(f"    存活 {k} 份: {tally[k]:3d} / {rounds}")
    return tally


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    span = 5
    print(f"两份同时启动 × {rounds} 轮,锁位段 span={span}(同进程两线程 / Linux 回环)\n")
    a = measure("A 组 —— 树上的实现(只问 p < mine,让位方向唯一)", rounds, span, patch=False)
    print()
    b = measure("B 组 —— 评审建议的改法(绑完问整段,两个方向都问)", rounds, span, patch=True)

    print("\n判读:")
    ok_a = a[0] == 0 and a[2] == 0
    print(f"  A 组恒等于 1 吗: {'是' if ok_a else '否'}"
          f"(0 存活 {a[0]} 轮 / 2 存活 {a[2]} 轮)"
          f" ⇒ {'让位方向唯一这条主张成立' if ok_a else '🔴 树上的实现自己就有问题'}")
    print(f"  B 组出现过 0 存活吗: {'是' if b[0] else '否'}({b[0]}/{rounds} 轮)"
          f" ⇒ {'“整段都问”确实会让业主双击后一个窗口都不开,驳回成立'
               if b[0] else '⚠️ 这一轮没复现出 0 存活 —— 驳回它的那句话就没有证据'}")
    print(f"  B 组出现过 2 存活吗: {b[2]}/{rounds} 轮")
    return 0 if (ok_a and b[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
