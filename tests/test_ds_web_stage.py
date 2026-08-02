#!/usr/bin/env python3
"""ds_web 写针孔 ⑩ `POST /api/projects/stage` 的 oracle
—— track opendesign-stage-history §7(切阶段)。

跑法:  python3 tests/test_ds_web_stage.py
纯 stdlib、离线、端口 0。

契约(design.md §7):薄壳,posture 逐条照抄既有 `_edit_change`:
  CT application/json → 0 < len ≤ OPEN_BODY_MAX → JSON dict + 键白名单
  {project, stage}(多余键即拒,防夹带 ds_root/today 走私)→ 两键都必须非空 str
  → ds_tools.set_stage(...)   ← 名字闸/词表/锁/页脚 bump 全在核心里
错误码:bad_stage 400 / project_not_found 404 / bad_name·path_escape 404。
**写口不回显词表**;词表由 `GET /api/projects` 的顶层 `stages` 下发,值 ==
ds_tools.PROJECT_STAGES(单一真相源,漂移即红)。

red-check:未实现前该路径落 do_POST 的兜底 → 404/405,happy 组红;
`/api/projects` 无 stages 键 → 词表组红。
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_common  # noqa: E402
import ds_tools  # noqa: E402
import ds_web  # noqa: E402

STAGE_PATH = "/api/projects/stage"
KEY = "翡翠湾-1801"
PROJ_MD = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 方案深化
- 当前状态: 等瓦工进场

## 变更记录

- [待确认] C1 2026-07-01 主卧灯位右移

---
最后更新: 2026-07-01
"""


def _mkroot() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_stage_")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    with open(os.path.join(d, "projects", f"{KEY}.md"), "w", encoding="utf-8") as fh:
        fh.write(PROJ_MD)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_stage_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(root: str):
    httpd = ds_web.make_server(root, _mkdist(), port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(port, body, path=STAGE_PATH, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    payload = (json.dumps(body).encode("utf-8") if isinstance(body, (dict, list))
               else body)
    headers = {"Content-Type": ctype} if ctype else {}
    conn.request("POST", path, body=payload, headers=headers)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    try:
        return r.status, json.loads(data.decode("utf-8"))
    except Exception:
        return r.status, None


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    try:
        return r.status, json.loads(data.decode("utf-8"))
    except Exception:
        return r.status, None


def _md(root, key=KEY):
    with open(os.path.join(root, "projects", f"{key}.md"), encoding="utf-8") as fh:
        return fh.read()


class StagePinholeHappy(unittest.TestCase):
    def test_sets_stage_on_disk(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "施工图"})
            self.assertEqual(200, st, body)
            self.assertTrue(body.get("ok"), body)
            self.assertEqual("施工图", body.get("stage"), body)
            self.assertEqual("方案深化", body.get("prev"), "应回传原阶段供 UI 播报")
        text = _md(root)
        self.assertIn("- 阶段: 施工图", text)
        self.assertNotIn("方案深化", text.split("## 变更记录")[0],
                         "头部不许残留旧阶段")

    def test_can_go_backwards(self):
        """返工很正常:允许回退到更早的阶段(核心语义,针孔不许加额外约束)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, _ = _post(port, {"project": KEY, "stage": "量房"})
            self.assertEqual(200, st)
        self.assertIn("- 阶段: 量房", _md(root))

    def test_bumps_last_updated(self):
        root = _mkroot()
        with _serve(root) as port:
            _post(port, {"project": KEY, "stage": "软装"})
        last = _md(root).rstrip().split("\n")[-1]
        self.assertTrue(last.startswith("最后更新:"), last)
        self.assertNotIn("2026-07-01", last, "页脚应 bump 到今天,不再是旧日期")

    def test_change_lines_untouched(self):
        root = _mkroot()
        before = [ln for ln in _md(root).split("\n") if ln.startswith("- [")]
        with _serve(root) as port:
            _post(port, {"project": KEY, "stage": "竣工验收"})
        after = [ln for ln in _md(root).split("\n") if ln.startswith("- [")]
        self.assertEqual(before, after, "改阶段不许碰变更行")


class StagePinholeRejects(unittest.TestCase):
    """一切拒绝路径:状态码对 + **档案逐字节不变**。"""

    def _reject(self, want_status, msg, **kwargs):
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            st, _ = _post(port, **kwargs)
        self.assertEqual(want_status, st, msg)
        self.assertEqual(before, _md(root), f"{msg}:拒绝路径必须零落盘")

    def test_stage_not_in_vocab(self):
        self._reject(400, "词表外的阶段应 400",
                     body={"project": KEY, "stage": "拆迁"})

    def test_stage_injection_attempts(self):
        for bad in ("施工图\n- 业主: [[黑客]]", "## 变更记录", "施工图 | 软装",
                    "- 阶段: 售后", "施工图\r\n最后更新: 2099-01-01"):
            with self.subTest(bad=bad):
                self._reject(400, f"注入尝试 {bad!r} 应被词表精确匹配挡下",
                             body={"project": KEY, "stage": bad})

    def test_unknown_project(self):
        self._reject(404, "不存在的项目应 404",
                     body={"project": "查无此项目", "stage": "施工图"})

    def test_name_gate(self):
        for bad in ("../../etc/passwd", "a/b", "..", "小区\\1801", "项目%2e%2e"):
            with self.subTest(bad=bad):
                self._reject(404, f"名字闸应挡下 {bad!r}",
                             body={"project": bad, "stage": "施工图"})

    def test_bad_content_type(self):
        self._reject(400, "非 json CT 应 400(CSRF 纵深)",
                     body={"project": KEY, "stage": "施工图"},
                     ctype="text/plain")
        self._reject(400, "缺 CT 应 400",
                     body={"project": KEY, "stage": "施工图"}, ctype="")

    def test_not_a_dict(self):
        for payload in (b"[]", b"\"x\"", b"123", b"null", b"{", b""):
            with self.subTest(payload=payload):
                self._reject(400, f"非对象 body {payload!r} 应 400", body=payload)

    def test_extra_keys_rejected(self):
        """多余键即拒:防夹带 ds_root/today 走私(同 _edit_change 先例)。"""
        for extra in ({"ds_root": "/etc"}, {"today": "2099-01-01"},
                      {"new_status": "已完成"}, {"cnum": 1}):
            with self.subTest(extra=extra):
                self._reject(400, f"夹带 {extra} 应 400",
                             body={"project": KEY, "stage": "施工图", **extra})

    def test_missing_or_wrong_types(self):
        for body in ({"project": KEY}, {"stage": "施工图"}, {},
                     {"project": "", "stage": "施工图"},
                     {"project": KEY, "stage": ""},
                     {"project": 1, "stage": "施工图"},
                     {"project": KEY, "stage": ["施工图"]},
                     {"project": None, "stage": None}):
            with self.subTest(body=body):
                self._reject(400, f"{body} 应 400", body=body)

    def test_oversized_body(self):
        big = json.dumps({"project": KEY, "stage": "施工图",
                          }).encode() + b" " * (ds_web.OPEN_BODY_MAX + 10)
        self._reject(400, "超尺寸 body 应 400", body=big)


class StagePinholeSurface(unittest.TestCase):
    def test_get_on_stage_path_not_allowed(self):
        """只读墙:GET 这条路径不许有内容面(405/404 都可,200 绝不可)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, _ = _get(port, STAGE_PATH)
        self.assertIn(st, (404, 405), f"GET {STAGE_PATH} 实得 {st}")

    def test_path_is_exact_match(self):
        """精确匹配,不是前缀:相邻路径不许被这条针孔接管。"""
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            for path in (STAGE_PATH + "/", STAGE_PATH + "x",
                         STAGE_PATH + "/../projects/stage"):
                with self.subTest(path=path):
                    st, _ = _post(port, {"project": KEY, "stage": "施工图"},
                                  path=path)
                    self.assertNotEqual(200, st, f"{path} 不该被接管")
        self.assertEqual(before, _md(root), "路径走私必须零落盘")

    def test_host_gate_inherited(self):
        """入口 Host 白名单(H2 修复)对新针孔同样生效。"""
        root = _mkroot()
        before = _md(root)
        with _serve(root) as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("POST", STAGE_PATH,
                         body=json.dumps({"project": KEY, "stage": "施工图"}),
                         headers={"Content-Type": "application/json",
                                  "Host": "evil.example.com"})
            st = conn.getresponse().status
            conn.close()
        self.assertNotEqual(200, st, "外部 Host 必须被拒(DNS rebinding)")
        self.assertEqual(before, _md(root))


# ══ track opendesign-stage-timer 追加(D5:可选 `since`)══════════════════════
# 契约扩张:键白名单 {project, stage} → {project, stage, since};since 可为
# null 或 `YYYY-MM-DD` 字符串。新错误码 invalid_since / since_in_future /
# since_before_prev 全部 400。**不新开端点。**
# red-check:未实现前 since 被当多余键 → 400,happy 组全红;
#           /api/projects 无 stage_since 键 → 透出组红。

PROJ_WITH_HIST_MD = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 方案深化

## 阶段历史

- 2026-06-01 洽谈
- 2026-07-20 方案深化

## 变更记录

- [待确认] C1 2026-07-01 主卧灯位右移

---
最后更新: 2026-07-01
"""


def _mkroot_hist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_stage_hist_")
    os.makedirs(os.path.join(d, "projects"), exist_ok=True)
    with open(os.path.join(d, "projects", f"{KEY}.md"), "w", encoding="utf-8") as fh:
        fh.write(PROJ_WITH_HIST_MD)
    return d


class StagePinholeSince(unittest.TestCase):
    """`since` 放行 + 三个新错误码 + 回传 since/days。"""

    def test_since_key_is_allowed_and_lands_on_disk(self):
        root = _mkroot_hist()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "施工图",
                                    "since": "2026-07-25"})
            self.assertEqual(200, st, body)
            self.assertTrue(body.get("ok"), body)
            self.assertEqual("2026-07-25", body.get("since"), body)
        self.assertIn("- 2026-07-25 施工图", _md(root),
                      "补录的日期必须真落盘,不是只在响应里")

    def test_since_null_is_same_as_absent(self):
        """`null` 等价"没给" ⇒ 走默认今天那条路,不许 400。"""
        root = _mkroot_hist()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "施工图",
                                    "since": None})
            self.assertEqual(200, st, body)
            self.assertEqual(ds_common.today_str(), body.get("since"), body)

    def test_days_is_zero_when_since_is_today(self):
        """days 由服务器按**本地**今天算 —— 用同一个 today_str 取基准,
        不写死日期,这条判据才不会隔天自己红。"""
        root = _mkroot_hist()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "施工图",
                                    "since": ds_common.today_str()})
            self.assertEqual(200, st, body)
            self.assertEqual(0, body.get("days"), body)

    def test_same_stage_with_since_is_the_backfill_path(self):
        """界面「设起始日」走的就是这条:阶段传当前值 + 给日期 = 纯补录。"""
        root = _mkroot_hist()
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": "方案深化",
                                    "since": "2026-07-10"})
            self.assertEqual(200, st, body)
            self.assertEqual("2026-07-10", body.get("since"), body)
        text = _md(root)
        self.assertIn("- 2026-07-10 方案深化", text)
        self.assertNotIn("- 2026-07-20 方案深化", text, "补录是改末条,不是追加")

    def test_since_bad_type_is_400(self):
        """类型闸:非 str 非 null 一律 400(镜像 due 的写法)。

        ⚠️ **这条现在就是绿的,而且实现后也绿 —— 它是护栏,不是判别式。**
        原因:壳层类型闸和"多余键"闸返回同一个通用 `bad request`,分不开。
        它的价值在实现之后(防类型闸被漏写),红检阶段不指望它红。
        真正把这一组钉住的是同类里那条会红的 happy 路径。"""
        for bad in (1, [], {}, True, 20260725):
            with self.subTest(bad=bad):
                root = _mkroot_hist()
                before = _md(root)
                with _serve(root) as port:
                    st, _ = _post(port, {"project": KEY, "stage": "施工图",
                                         "since": bad})
                self.assertEqual(400, st, f"since={bad!r} 应 400")
                self.assertEqual(before, _md(root), "类型不对必须零落盘")

    def _reject_hist(self, since, code, msg, stage="施工图"):
        """⚠️ **必须断言具体错误码,不能只断言 400。**
        只断 400 的话,今天 `since` 会被"多余键"闸拒掉 → 照样 400 → 判据**假绿**,
        实现完了也分不出"日期闸真的生效"还是"键闸顺手挡了"。
        断错误码就红得对:现在返回的是 `bad request`,不是 `invalid_since`。"""
        root = _mkroot_hist()
        before = _md(root)
        with _serve(root) as port:
            st, body = _post(port, {"project": KEY, "stage": stage, "since": since})
        self.assertEqual(400, st, msg)
        self.assertEqual(code, (body or {}).get("error"),
                         f"{msg}:错误码必须是 {code},不能被通用 bad request 顶替")
        self.assertEqual(before, _md(root), f"{msg}:拒绝路径必须零落盘")

    def test_invalid_since_is_400(self):
        for bad in ("2026-7-25", "25-07-2026", "2026/07/25", "昨天", "",
                    "2026-13-01", "2026-02-30", "2026-07-25T00:00"):
            with self.subTest(bad=bad):
                self._reject_hist(bad, "invalid_since", f"{bad!r} 应 invalid_since")

    def test_since_in_future_is_400(self):
        self._reject_hist("2099-01-01", "since_in_future", "未来的起始日应被拒")

    def test_since_before_prev_is_400(self):
        """比段末那条(2026-07-20)还早 ⇒ 乱序,拒。"""
        self._reject_hist("2026-07-19", "since_before_prev", "早于上一条应被拒")

    def test_since_cannot_smuggle_injection(self):
        """日期字段同样是写口:换行/字段注入必须被**格式闸**挡死
        (而不是被别的闸碰巧挡住 —— 所以同样断错误码)。"""
        for bad in ("2026-07-25\n- 阶段: 售后", "2026-07-25\r\n最后更新: 2099-01-01",
                    "2026-07-25 施工图"):
            with self.subTest(bad=bad):
                self._reject_hist(bad, "invalid_since", f"注入 {bad!r} 应被格式闸拒")

    def test_extra_keys_still_rejected_alongside_since(self):
        """放行一个新键不等于放松白名单:走私键照旧即拒。"""
        root = _mkroot_hist()
        before = _md(root)
        with _serve(root) as port:
            st, _ = _post(port, {"project": KEY, "stage": "施工图",
                                 "since": "2026-07-25", "today": "2099-01-01"})
        self.assertEqual(400, st, "夹带 today 应 400")
        self.assertEqual(before, _md(root))


class StageTimerExposure(unittest.TestCase):
    """读侧透出:`/api/projects` 每项带 stage_since / stage_days。
    **必须调 ds_tools.stage_timer,不许第三份解析**(D4)。"""

    def test_projects_exposes_stage_timer_fields(self):
        root = _mkroot_hist()
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        p = next(x for x in body["projects"] if x["key"] == KEY)
        self.assertEqual("2026-07-20", p.get("stage_since"), p)
        self.assertIsInstance(p.get("stage_days"), int, p)

    def test_legacy_project_is_null_not_zero(self):
        """没有阶段历史段的旧档案 ⇒ 两个字段**存在且为 null**。
        **不是 0** —— 0 会在界面上显示成「0 天」,是个假数字。

        ⚠️ 必须先断言**键存在**再断言值:只写 `.get(...) is None` 的话,
        "字段压根没实现"也会照绿(键不存在,`.get` 同样返回 None)。"""
        root = _mkroot()          # 无 `## 阶段历史` 段的旧格式
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        p = next(x for x in body["projects"] if x["key"] == KEY)
        self.assertIn("stage_since", p, "字段必须存在(哪怕值是 null)")
        self.assertIn("stage_days", p, "字段必须存在(哪怕值是 null)")
        self.assertIsNone(p["stage_since"], p)
        self.assertIsNone(p["stage_days"], p)

    def test_matches_ds_tools_stage_timer_exactly(self):
        """锚断言:网页那条读路径与 ds_tools 的算法必须给出同一个答案。
        没有这条,「两边各自解析、一起错成同一个值」会照绿。"""
        root = _mkroot_hist()
        with _serve(root) as port:
            _, body = _get(port, "/api/projects")
        p = next(x for x in body["projects"] if x["key"] == KEY)
        want = ds_tools.stage_timer(_md(root))
        self.assertEqual(want["since"], p.get("stage_since"))
        self.assertEqual(want["days"], p.get("stage_days"))


class StageVocabDelivery(unittest.TestCase):
    """词表单一真相源:前端不许硬编码副本 —— 由 /api/projects 下发。"""

    def test_projects_carries_stages(self):
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        self.assertIn("stages", body, "应下发阶段词表")
        self.assertEqual(list(ds_tools.PROJECT_STAGES), body["stages"],
                         "词表必须与 ds_tools.PROJECT_STAGES 逐项一致(含顺序)")

    def test_projects_still_lists_projects(self):
        """加字段不许改既有形状(回归)。"""
        root = _mkroot()
        with _serve(root) as port:
            st, body = _get(port, "/api/projects")
        self.assertEqual(200, st)
        keys = [p["key"] for p in body["projects"]]
        self.assertIn(KEY, keys)
        stages = {p["key"]: p["stage"] for p in body["projects"]}
        self.assertEqual("方案深化", stages[KEY])


if __name__ == "__main__":
    unittest.main(verbosity=2)
