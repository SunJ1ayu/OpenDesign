"""探针:b8(双击两下只许一份赢)在总跑里红了一次,先问"是不是真 bug"。

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

tmp = Path(tempfile.mkdtemp(prefix="b8probe-"))
winners = {}        # port -> round
procs = []
bad = 0
ROUNDS = int(os.environ.get("ROUNDS", "12"))
for r in range(ROUNDS):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); base = s.getsockname()[1]; s.close()
    go = tmp / f"go{r}"
    ps = [subprocess.Popen([sys.executable, "-c", t.LOCK_CHILD, BIN, str(base), "5",
                            str(tmp / f"shown{r}-{i}.txt"), str(go)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
          for i in range(2)]
    procs += ps
    time.sleep(0.3)
    go.write_text("go", encoding="utf-8")
    got = [json.loads(p.stdout.readline()) for p in ps]
    won = [g for g in got if g["acquired"]]
    span = list(range(base, base + 5))
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
