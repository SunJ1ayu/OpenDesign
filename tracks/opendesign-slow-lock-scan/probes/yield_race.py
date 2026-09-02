"""两份同时启动时,让位方向唯一 vs 整段都问 —— 到底活下来几份。

为什么有这支探针(2026-09-02):`bin/ds_shell_core.py` 的 `_someone_ahead_of` 里写着
"改成整段都问是不行的,我量过:两份同时启动时会双向让位,3 轮里有 1 轮存活 0 份"。
第二轮评审的两条腿(subdeepseek 与被砍前的 subkimi)**各自独立**指出:
这个数是驳回"唯一能堵住拓扑盲区的便宜修法"的**全部依据**,而仓库里没有它的探针、
没有收据、没有对照组 —— 正是这一单自己刚给 connect_latency 补掉的那个形态
("量出来的数活在文档里,仓库里复现不出来")。所以补这一支。

它量两件事,因为这是一笔**取舍**,不是单指标:
  (1) **盲区场景**:陌生程序占过 base 又退出 ⇒ 第一份在 base+1、第二份快扫全瞎绑上 base。
      放行 = 两份 OpenDesign 并存 = 数据面出事。
  (2) **同时启动 × N 轮**:业主双击两下,最后活下来几份。0 份 = 一个窗口都不开。

三组实现:
  A 组 = 树上的实现:`_someone_ahead_of` 只问 `p < mine`(让位方向唯一)
  B 组 = 评审腿建议的改法:绑完之后问**整段**(除了自己),两个方向都问
  C 组 = 主 agent 自己构造的**最强变体**(2026-09-02,用来攻"B 组是不是稻草人"):
         只有绑上首选锁位 base 的那份才回头问后面,其余仍只问前面。
         为什么它最强:盲区里第二份恰好绑在 base 上,只有让它回头问才够得着;
         而非 base 那一侧的让位方向仍然唯一。

判读:
  A 组的 (2) 必须**恒等于 1**;它的 (1) 今天是**放行**(这就是那条已记账的拓扑盲区)。
  B/C 组的 (2) 出现 0 ⇒ 在**那一种启动情态下**堵住数据面的代价是业主双击后没窗口。

  ⛔ **别拿 (2) 单独下结论 —— 判读以 (3) 为准。**
  这份 docstring 原本写的是"B/C 只要 (2) 出现过 0,这条修法就被证伪 ⇒ 必须给锁协议
  加先来后到字段"。那句话**已经被本探针自己的 (3) 段推翻**(2026-09-02):(2) 用
  `threading.Barrier` 把两份对齐到同一瞬间,而错开 2ms 以上,B/C 的 0 存活五遍
  (30/40/40/20/20 轮)里一次都没再出现(**2.0ms 这一档本身只跑过四遍**:第一遍
  走的是 0/10/50/200/500 这几档,没有 2.0ms 格 —— "五遍"说的是"≥2ms 的档",
  别把它读成"2.0ms 那一格量过五遍") ⇒ 危险窗口只有 1~2ms 量级,是一笔**取舍**,不是"行不通"。
  保留原话在这里是为了让判错查得到(见 verify.md findings 10 / deviation 1)。

⚠️ 它模的是什么、不是什么:同一个进程里的两个线程、Linux 回环。真实场景是业主那台
   Windows 上的两个进程。**竞争窗口的绝对宽度会不一样**,所以这里的比例别当成
   业主那台机器上的概率;能被它证伪的是"B 组结构上会不会出现 0 存活"这件事本身。
"""
import os
import socket
import sys
import threading
import time
from unittest import mock

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
    """B 组:绑完之后问整段(除了自己)—— 评审腿建议的修法。"""
    return self._scan((p for p in self._ports() if p != mine), patient=True) is not None


def ask_base_looks_behind(self, mine: int) -> bool:
    """C 组:只有绑上首选锁位的那份才回头问后面,其余仍只问前面。"""
    ports = list(self._ports())
    others = (p for p in ports if p != mine) if mine == ports[0] else (p for p in ports if p < mine)
    return self._scan(others, patient=True) is not None


def blindspot_lets_a_second_through(patch) -> bool:
    """(1) 盲区场景:True = 开出了第二份(坏)。

    摆场子:陌生程序占住 base ⇒ 第一份只能落在 base+1 ⇒ 陌生程序退出 ⇒ base 空出来。
    然后把第二份的 connect 期限注入成 0(实测 BlockingIOError,快扫必然全瞎),
    看它会不会宣布自己是唯一的。第一份在注入**之前**就位,所以它自己不受影响。
    """
    span = 5
    base = free_base(span)
    stranger = socket.socket()
    stranger.bind(("127.0.0.1", base))
    stranger.listen(1)
    first = core.InstanceLock(base_port=base, span=span)
    assert first.acquire() is True, "场子没摆起来:第一份就没拿到锁"
    assert first.port == base + 1, f"场子没摆对:第一份落在 {first.port},不是 base+1"
    stranger.close()
    original = core.InstanceLock._someone_ahead_of
    if patch is not None:
        core.InstanceLock._someone_ahead_of = patch
    try:
        real = core.lock_timeouts()
        with mock.patch.object(core, "lock_timeouts", return_value={**real, "connect": 0}):
            second = core.InstanceLock(base_port=base, span=span)
            got = second.acquire()
            second.release()
        return got is True
    finally:
        core.InstanceLock._someone_ahead_of = original
        first.release()


def one_round(base: int, span: int, offset_s: float = 0.0) -> int:
    """两份 acquire(),返回活下来几份。

    `offset_s` = 第二份比第一份晚多久开始(0 = Barrier 对齐的近同时启动)。
    加它的理由(2026-09-02,第三轮评审 subglm 与我自审 D2 各自独立命中):
    此前只量过 Barrier 对齐这一种情态,而业主是双击两下,中间隔着几百毫秒。
    """
    ready = threading.Barrier(2)
    locks = [core.InstanceLock(base_port=base, span=span) for _ in range(2)]
    got = [None, None]

    def run(i):
        ready.wait()
        if i == 1 and offset_s:
            time.sleep(offset_s)
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


def measure(label: str, rounds: int, span: int, patch, offset_s: float = 0.0) -> dict:
    original = core.InstanceLock._someone_ahead_of
    if patch is not None:
        core.InstanceLock._someone_ahead_of = patch
    try:
        tally = {0: 0, 1: 0, 2: 0}
        for _ in range(rounds):
            tally[one_round(free_base(span), span, offset_s)] += 1
    finally:
        core.InstanceLock._someone_ahead_of = original
    print(f"{label}")
    for k in (0, 1, 2):
        print(f"    存活 {k} 份: {tally[k]:3d} / {rounds}")
    return tally


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    span = 5

    print("(1) 盲区场景 —— 第二份有没有被放行(True = 两份并存 = 数据面出事)")
    blind = {}
    for label, patch in (("A 树上的实现", None),
                         ("B 问整段  ", ask_whole_range),
                         ("C base回头看", ask_base_looks_behind)):
        blind[label] = blindspot_lets_a_second_through(patch)
        print(f"    {label}: {'放行(坏)' if blind[label] else '堵住'}")

    print(f"\n(2) 两份同时启动 × {rounds} 轮,锁位段 span={span}(同进程两线程 / Linux 回环)")
    a = measure("\n  A 组 —— 树上的实现(只问 p < mine,让位方向唯一)", rounds, span, None)
    b = measure("\n  B 组 —— 评审腿建议的改法(绑完问整段,两个方向都问)", rounds, span, ask_whole_range)
    c = measure("\n  C 组 —— 最强变体(只有 base 上那份回头问后面)", rounds, span, ask_base_looks_behind)

    print("\n判读(这是一笔取舍,不是单指标):")
    rows = [("A 树上的实现", blind["A 树上的实现"], a),
            ("B 问整段", blind["B 问整段  "], b),
            ("C base回头看", blind["C base回头看"], c)]
    for name, lets_through, tally in rows:
        both = (not lets_through) and tally[0] == 0 and tally[2] == 0
        print(f"    {name:<14} 盲区{'放行' if lets_through else '堵住'}"
              f"  同时启动 0 存活 {tally[0]:>2}/{rounds}"
              f"  ⇒ {'两件事都做到了' if both else '做不到两全'}")
    ok = any((not l) and t[0] == 0 and t[2] == 0 for _, l, t in rows)
    # ⛔ 这一段只量了 Barrier 对齐这一种启动情态,**它判不出"必须加先来后到字段"** ——
    #    那句旧结论 2026-09-02 已被下面 (3) 段的错开扫描推翻(第四轮评审 subkimi 指出:
    #    墓碑当时只立在 verify.md,而工具每跑一遍还在照印旧结论)。这里只报事实,不下判决。
    print(f"\n    在**对齐启动**这一种情态下有没有哪一组两件事都做到了: {'有' if ok else '没有'}")
    print("    ⛔ 到此为止不许下结论:对齐启动是最坏情态,危险窗口有多宽由 (3) 段的错开扫描说了算。")

    print("\n(3a) 一次 acquire 到底要多久 —— 「危险窗口有多宽」必须由它解释,否则那句话不自证")
    durs = []
    for _ in range(60):
        b = free_base(span)
        lk = core.InstanceLock(base_port=b, span=span)
        t0 = time.perf_counter()
        lk.acquire()
        durs.append((time.perf_counter() - t0) * 1000.0)
        lk.release()
    durs.sort()
    print(f"    空段上单份 acquire 耗时(60 次,ms): 中位 {durs[len(durs)//2]:.3f}"
          f"  p90 {durs[int(len(durs)*0.9)]:.3f}  max {durs[-1]:.3f}")
    print("    ⇒ 双向让位要求两份都在对方**扫描之前**绑好,所以危险窗口的量级 = 这个耗时的量级。")

    print("\n(3) 错开启动 —— (2) 量的是 Barrier 对齐,而业主是双击两下,中间隔着几百毫秒")
    print("""    判读规则(**写在看结果之前**,2026-09-02):
    - B/C 在每一档错开上**都还**出现 0 存活 ⇒ "做不到两全"与错开无关,驳回原样成立。
    - B/C 的 0 存活在某一档之后**消失** ⇒ 那一档就是**危险窗口的宽度**;
      "做不到两全"必须限定成"两份的 acquire 落进这个窗口时",而这一单该不该当场修,
      取决于真实场景里两次 acquire 有多容易落进去。
      ⚠️ 别把"点击间隔"当成"acquire 间隔":进程冷启动的抖动比点击间隔大得多。
    - A 组只要有一档不再恒等于 1 存活 ⇒ **探针坏了**,(3) 整段都不作数。""")
    offsets_ms = ([float(x) for x in sys.argv[2].split(",")]
                  if len(sys.argv) > 2 else [0, 10, 50, 200, 500])
    grid = {}
    for name, patch in (("A 树上的实现", None),
                        ("B 问整段", ask_whole_range),
                        ("C base回头看", ask_base_looks_behind)):
        for off in offsets_ms:
            grid[(name, off)] = measure(f"\n  {name} · 错开 {off}ms", rounds, span, patch, off / 1000.0)

    print(f"\n  汇总:每格 = 存活 0 份的轮数 / {rounds}(A 组必须恒为 0)")
    print("    " + "组".ljust(14) + "".join(f"{o:g}ms".rjust(9) for o in offsets_ms))
    for name in ("A 树上的实现", "B 问整段", "C base回头看"):
        print("    " + name.ljust(14)
              + "".join(f"{grid[(name, o)][0]}/{rounds}".rjust(9) for o in offsets_ms))

    a_broken = [o for o in offsets_ms if grid[("A 树上的实现", o)][1] != rounds]
    if a_broken:
        print(f"\n    ⚠️ A 组在 {a_broken} 上不是恒 1 存活 ⇒ 探针坏了,(3) 不作数")
        return 0
    bad = {n: [o for o in offsets_ms if grid[(n, o)][0] > 0] for n in ("B 问整段", "C base回头看")}
    for n, offs in bad.items():
        if offs == offsets_ms:
            print(f"\n    {n}: 每一档都出现 0 存活 ⇒ 与错开无关")
        elif offs:
            print(f"\n    {n}: 只在错开 {offs} 上出现 0 存活 ⇒ 危险窗口宽度 ≈ 最大的那一档")
        else:
            print(f"\n    {n}: 任何一档都没出现 0 存活 ⇒ **本轮证伪了'与错开无关'**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
