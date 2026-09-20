"""T0 探针:apply 侧那段"作废备货"到底还走不走得到?(design.md 的 D1)

为什么要它:#24 的修法取决于这个答案。判读规则**写在看结果之前**:

  A. 真实链路(startup 说 install → 前端才调 apply)下 `attempted` 能进作废分支
     ⇒ 是**活的**纵深,#24 改常量(`== "attempted"` → `in PERMANENT_BLOCKERS`),注释照实写。
  B. 真实链路下两种都进不去,但直接调 apply(端点本身是暴露的)能进
     ⇒ 是**纵深专用**代码,#24 仍改常量,但注释必须说明"正常链路 startup 已拦",不许再暗示它是主防线。
  C. 两种调法都进不去 ⇒ 死代码,#24 改为删除或明写死因,并补一条钉住 startup 拦截的判据。

不改任何被测代码;只把 discard_ready 换成会记账的替身。
"""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "bin"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import ds_update_apply          # noqa: E402
import ds_update_startup        # noqa: E402
import ds_auto_update           # noqa: E402
import test_ds_update_eligibility as el   # noqa: E402

LOG = []


class Probe(el.UpdateEligibility):
    def _run_chain(self, label, env, preflight=None, record=False):
        """按前端真实顺序跑:GET /api/update/startup → (若说 install)POST /api/update/apply。"""
        path, _ = self._stock()
        if record:
            ds_auto_update.record_attempt(self.data_root, el.LATEST)
        self._armed()
        calls = []
        real_discard = ds_update_startup.discard_ready

        def spy(root):
            calls.append(root)
            return real_discard(root)

        ctx = mock.patch.object(ds_update_apply, "update_preflight_problem",
                                lambda paths: (preflight, "探针"))
        with mock.patch.object(ds_update_startup, "discard_ready", spy), \
                mock.patch.dict(os.environ, env or {}):
            with (ctx if preflight else _null()):
                with self._serve() as port:
                    _st, startup = el._get(port, "/api/update/startup")
                    applied = None
                    if startup.get("action") == "install":
                        _st2, applied = el._post(port, "/api/update/apply", el.AUTO)
                    # 纵深问法:不管 startup 说什么,直接调一次 apply(端点是暴露的)
                    direct_calls_before = len(calls)
                    _st3, direct = el._post(port, "/api/update/apply", el.AUTO)
        LOG.append({
            "场景": label,
            "startup": startup.get("action"),
            "startup_reason": startup.get("reason"),
            "真实链路是否调到 apply": applied is not None,
            "真实链路 apply stage": (applied or {}).get("stage"),
            "真实链路进了作废分支": len(calls) > 0 and direct_calls_before > 0,
            "直接调 apply 的 stage": direct.get("stage"),
            "直接调 apply 进了作废分支": len(calls) > direct_calls_before,
            "包还在": self._package_exists(path),
        })

    # 🔴 一个场景一个 test 方法 = 一个场景一个全新 data_root。
    #    第一版把四个场景塞进同一个方法,第一个场景写的那笔账污染了第四个
    #    (干净场景回 reason=attempted)⇒ 读数作废。错的是探针,不是产品。
    def test_a_attempted(self):
        self._run_chain("attempted(账上记过一次)", None, record=True)

    def test_b_path_unsupported(self):
        self._run_chain("path_unsupported(永久)", None, preflight="path_unsupported")

    def test_c_no_shell(self):
        self._run_chain("no_shell(临时)", {"DS_SHELL_LOCK_PORT": ""})

    def test_d_clean(self):
        self._run_chain("干净(应当真装)", None)


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


if __name__ == "__main__":
    # 只跑本探针自己的四个方法 —— 继承 el 那一卷是为了借夹具,不是把它重跑一遍
    # (同 el 卷文件头那条教训:借夹具不是继承考题)。
    suite = unittest.TestSuite(
        Probe(n) for n in sorted(n for n in dir(Probe)
                                 if n.startswith("test_") and n in Probe.__dict__))
    r = unittest.TextTestRunner(verbosity=0).run(suite)
    print("\n=== T0 读数 ===")
    for row in LOG:
        print("  " + " | ".join("%s=%s" % (k, v) for k, v in row.items()))
    print("\n失败/错误:", len(r.failures), len(r.errors))
    for t, tb in r.failures + r.errors:
        print(tb[-1200:])
