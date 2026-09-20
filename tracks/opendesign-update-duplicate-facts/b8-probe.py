"""探针:b8(双击两下只许一份赢)在总跑里红了一次,先问"是不是真 bug"。

**本单的工作副本**(track opendesign-update-duplicate-facts,上一单延期的 LOW #27)。
来历:`tracks/archive/opendesign-startup-not-blocked-by-update/b8-probe.py` —— **归档原件一个字没动**。

🔴 **改了什么,以及为什么**:归档那版把锁位数写死成 `range(base, base + 5)` = **5 个槽**,
而 `InstanceLock._ports` 是 `range(base_port, base_port + span + 1)`、`span=5` ⇒ **6 个槽**。
落在第 6 个槽(`base+5`)上的"上几轮赢家"根本不会被残留统计看见 ⇒ 上一单那句
"25 轮 0 异常、残留不是原因"要打个折。修法**不是把 5 改成 6**(那只是把抄错的数字抄对,
`span` 一改又错),而是**从 `InstanceLock` 自己算**:同一个事实只许有一处来源,
这正是本单整单在治的那种病。SPAN_CHECK 那一段是这件事的机械断言(判据 T4)。

复刻 b8 的循环,但把它**没打印**的两件事打出来:每轮的 base,以及上一轮留活的赢家在哪个端口。
b8 每轮的赢家 `time.sleep(120)` 不退(cleanup 要等整条用例结束),而下一轮的 span 是
base..base+4 —— Linux 的临时端口是近似递增发的,所以后一轮的 span **很可能罩住前一轮的赢家**。
真是这样的话:两个新实例都正确地看见"已经有一份在跑"、都让位 ⇒ 0 个赢家,
而 b8 断言"必须恰好 1 个" ⇒ **红的是题面,产品做对了**(判据自己造了第三份实例)。

这个结论不许靠讲道理成立,所以这里打印机械证据:命中端口 == 前面某一轮的赢家端口。
"""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BIN = str(REPO / "bin")
sys.path.insert(0, str(REPO / "tests"))
import test_ds_shell_core as t                      # noqa: E402  借它的 LOCK_CHILD,不改它
sys.path.insert(0, BIN)
import ds_shell_core as core                       # noqa: E402  锁位数问它,不自己写数字

SPAN = 5                                           # 传给 LOCK_CHILD 的 span(子进程照此建锁)
_PORTS = list(core.InstanceLock(base_port=0, span=SPAN)._ports())
# T4:探针量的槽数必须与产品真用的槽数一致。不一致就别往下跑 —— 一个量错范围的探针
# 会给出"残留不是原因"这种**看起来很干净**的结论,而那正是最难被发现的假绿。
assert len(_PORTS) == SPAN + 1, "锁位数对不上:%r" % (_PORTS,)
print("锁位数 = %d(由 InstanceLock._ports 推导,span=%d)" % (len(_PORTS), SPAN))

tmp = Path(tempfile.mkdtemp(prefix="b8probe-"))
winners = {}        # port -> round
procs = []
bad = 0
ROUNDS = int(os.environ.get("ROUNDS", "12"))
for r in range(ROUNDS):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); base = s.getsockname()[1]; s.close()
    go = tmp / f"go{r}"
    ps = [subprocess.Popen([sys.executable, "-c", t.LOCK_CHILD, BIN, str(base), str(SPAN),
                            str(tmp / f"shown{r}-{i}.txt"), str(go)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
          for i in range(2)]
    procs += ps
    time.sleep(0.3)
    go.write_text("go", encoding="utf-8")
    got = [json.loads(p.stdout.readline()) for p in ps]
    won = [g for g in got if g["acquired"]]
    span = [base + off for off in _PORTS]        # ← 归档版写死 base+5(少一个槽)
    stale = {p: rr for p, rr in winners.items() if p in span}
    mark = "ok " if len(won) == 1 else "🔴 "
    if len(won) != 1:
        bad += 1
    print(f"{mark}第{r}轮 base={base} span={span[0]}..{span[-1]} 结果={got} "
          f"落在本轮 span 里的**上几轮赢家**={stale or '无'}")
    for g in won:
        winners[g["port"]] = r

for p in procs:
    p.kill()
print(f"\n{ROUNDS} 轮里 {bad} 轮不是恰好一个赢家")
