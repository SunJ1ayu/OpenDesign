#!/usr/bin/env python3
"""ds_web 只读 API oracle — track opendesign-workbench-p2 T1(design.md Test strategy)。

跑法:  python3 tests/test_ds_web_api.py
覆盖四条只读 GET:
  /api/projects                     项目列表(key/name/stage/open_count/delivered/last_update)
  /api/projects/<key>/changes       该项目全量变更(四状态,可选字段缺省)
  /api/projects/<key>/refs          该项目参考图(过滤 refs-index 用于:)
  /api/refs/file/<path>             参考图静态服务(三闸:字符集/realpath/扩展白名单)

red-check(commit message 附结果):对 refs 静态服务三闸各做一次突变验红——
  Gate A 字符集:注释掉字符集白名单 → test_file_charset_gate 变红(bad!.png 被误服务)
  Gate B realpath:注释掉 within 前缀闸 → test_file_symlink_escape / test_file_traversal 变红
  Gate C 扩展白名单:注释掉扩展闸 → test_file_ext_whitelist 变红(refs/notes.txt 被误服务)

纯 stdlib、离线、端口 0,不烧 LLM。
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_todo  # noqa: E402
import ds_web   # noqa: E402


PROJ_A = """# 保利中央公园 2803

- 业主: [[张伟]]
- 阶段: 施工图
- 开始日期: 2026-05-01
- 当前状态: 玄关柜待业主确认

## 变更记录
- [待确认] C12 2026-07-09 【玄关】玄关柜整体改到 2.4 米高,柜顶留 300mm 检修口
- [进行中] C11 2026-07-08 电视墙改用岩板,取消原定木格栅
- [已完成] C8 2026-06-28 全屋筒灯统一换 3000K
- [已关闭] C7 2026-06-20 沙发背景墙两侧加壁灯(业主取消)
- [待确认] 缺编号缺日期的残缺行也要能解析

## 沟通日志
- 2026-07-09 现场:太太提玄关柜改高

---
最后更新: 2026-07-10
"""

PROJ_DELIVERED = """# 翡翠湾-1801

- 业主: [[李四]]
- 阶段: 竣工验收

## 变更记录
- [已完成] C1 2026-06-01 全屋交付

---
最后更新: 2026-06-30
"""

PROJ_BARE = """# 光头项目

没有阶段、没有变更、没有页脚——读侧必须宽容不崩。
"""


def _mkroot(files: dict, refs_index: str | None = None) -> str:
    d = tempfile.mkdtemp(prefix="ds_web_api_")
    proj = os.path.join(d, "projects")
    os.makedirs(proj)
    for name, text in files.items():
        mode = "wb" if isinstance(text, bytes) else "w"
        kw = {} if isinstance(text, bytes) else {"encoding": "utf-8"}
        with open(os.path.join(proj, name), mode, **kw) as fh:
            fh.write(text)
    os.makedirs(os.path.join(d, "refs"))
    if refs_index is not None:
        with open(os.path.join(d, "refs-index.md"), "w", encoding="utf-8") as fh:
            fh.write(refs_index)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_api_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


def _write_bytes(path: str, data: bytes = b"\x89PNG\r\n\x1a\n"):
    with open(path, "wb") as fh:
        fh.write(data)


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


def _req(port: int, path: str, method: str = "GET"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path)
    r = conn.getresponse()
    body = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hd, body


def _get_json(port: int, path: str):
    st, hd, body = _req(port, path)
    return st, hd, (json.loads(body.decode("utf-8")) if body else None)


# ── /api/projects ────────────────────────────────────────────────────────────
class TestProjects(unittest.TestCase):

    def test_projects_list(self):
        root = _mkroot({"保利中央公园.md": PROJ_A, "翡翠湾-1801.md": PROJ_DELIVERED})
        with _serve(root) as port:
            st, hd, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertIn("charset=utf-8", hd["content-type"].lower())
        by_key = {p["key"]: p for p in d["projects"]}
        a = by_key["保利中央公园"]
        self.assertEqual(a["name"], "保利中央公园 2803")
        self.assertEqual(a["stage"], "施工图")
        self.assertEqual(a["delivered"], False)
        self.assertEqual(a["last_update"], "2026-07-10")
        # open_count 与 ds_todo 同源:待确认(C12 + 残缺行)+ 进行中(C11) = 3
        self.assertEqual(a["open_count"], 3)
        d1 = by_key["翡翠湾-1801"]
        self.assertEqual(d1["delivered"], True)   # 竣工验收 = 已交付
        self.assertEqual(d1["open_count"], 0)

    def test_projects_open_count_matches_collect(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        collected = ds_todo.collect(root)
        want = sum(1 for it in collected["open"] if it["project"] == "保利中央公园")
        got = {p["key"]: p for p in d["projects"]}["保利中央公园"]["open_count"]
        self.assertEqual(got, want)

    def test_projects_empty(self):
        with _serve(_mkroot({})) as port:
            st, _, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        self.assertEqual(d["projects"], [])

    # 硬化(panel subsense LOW):projects/ 里指向外部的 symlink .md 不读不列
    def test_projects_symlink_md_excluded(self):
        if not hasattr(os, "symlink"):
            self.skipTest("平台无 symlink")
        root = _mkroot({"保利中央公园.md": PROJ_A})
        outer = os.path.join(root, "outer-secret.md")
        with open(outer, "w", encoding="utf-8") as fh:
            fh.write("# 泄露的外部标题\n\n- 阶段: 不该看见\n")
        os.symlink(outer, os.path.join(root, "projects", "泄露.md"))
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        keys = {p["key"] for p in d["projects"]}
        self.assertEqual(keys, {"保利中央公园"})  # symlink 条目整个不出现
        self.assertNotIn("泄露的外部标题", json.dumps(d, ensure_ascii=False))

    def test_projects_bare_md_tolerant(self):
        root = _mkroot({"光头项目.md": PROJ_BARE})
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects")
        self.assertEqual(st, 200)
        p = d["projects"][0]
        self.assertEqual(p["key"], "光头项目")
        self.assertEqual(p["open_count"], 0)
        self.assertEqual(p["last_update"], None)
        self.assertIn(p["stage"], ("", None))

    # ── p7:联合工作区项目夹(design D2)────────────────────────────────────
    def _add_workspace(self, root, folders, mapping=None):
        ws = os.path.join(root, "ws")
        for f in folders:
            os.makedirs(os.path.join(ws, "01-项目", f), exist_ok=True)
        os.makedirs(os.path.join(root, "config"), exist_ok=True)
        with open(os.path.join(root, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": ws, "projects": mapping or {}}, fh,
                      ensure_ascii=False)
        return ws

    def test_projects_union_unregistered(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_DELIVERED})
        self._add_workspace(root, ["20260701 新签 云璟台 3#301"])
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        by_key = {p["key"]: p for p in d["projects"]}
        self.assertFalse(by_key["翡翠湾-1801"]["unregistered"])
        u = by_key["20260701 新签 云璟台 3#301"]
        self.assertTrue(u["unregistered"])
        self.assertEqual(u["name"], "20260701 新签 云璟台 3#301")
        self.assertEqual(u["open_count"], 0)

    def test_projects_union_consumed_not_duplicated(self):
        # 被 token 自动绑定消费(翡翠湾-1801 ↔ 含两 token 的唯一文件夹)与被
        # 显式映射消费(保利中央公园)的文件夹都不重复出现为未建档条目
        root = _mkroot({"翡翠湾-1801.md": PROJ_DELIVERED, "保利中央公园.md": PROJ_A})
        self._add_workspace(
            root, ["20260601 平湖 翡翠湾 3#1801", "20260501 保利大盘"],
            mapping={"保利中央公园": "01-项目/20260501 保利大盘"})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        keys = sorted(p["key"] for p in d["projects"])
        self.assertEqual(keys, ["保利中央公园", "翡翠湾-1801"])

    # ── depth2 track:projectsDepth=2 分组工作区 ──────────────────────────
    def _add_grouped_workspace(self, root, rels, mapping=None):
        ws = os.path.join(root, "ws")
        for rel in rels:
            os.makedirs(os.path.join(ws, *rel.split("/")), exist_ok=True)
        os.makedirs(os.path.join(root, "config"), exist_ok=True)
        with open(os.path.join(root, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": ws, "projects": mapping or {},
                       "projectsDir": ".", "projectsDepth": 2}, fh,
                      ensure_ascii=False)
        return ws

    def test_projects_union_grouped(self):
        root = _mkroot({})
        self._add_grouped_workspace(
            root, ["2025/0605 某项目", "2026/0315 某项目"])
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        by_key = {p["key"]: p for p in d["projects"]}
        u = by_key["2026:0315 某项目"]
        self.assertTrue(u["unregistered"])
        self.assertEqual(u["group"], "2026")
        self.assertEqual(u["name"], "0315 某项目")
        self.assertIn("2025:0605 某项目", by_key)

    def test_projects_grouped_consumed_not_duplicated(self):
        # 显式映射指向分组内项目夹 → 该文件夹不重复出现为未建档条目
        root = _mkroot({"翡翠湾-1801.md": PROJ_DELIVERED})
        self._add_grouped_workspace(
            root, ["2026/0315 某项目"],
            mapping={"翡翠湾-1801": "2026/0315 某项目"})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        keys = sorted(p["key"] for p in d["projects"])
        self.assertEqual(keys, ["翡翠湾-1801"])

    # ── cockpit 速览字段(owner/status_note)**已整条下线**(2026-07-28)────────
    # 两个字段都只有一个消费者 = 伴随列速览块,而那个块已按用户要求删掉:
    #   · status_note(档案「当前状态」):17 个 MCP 工具**没有一个写它**,建档时由模板
    #     填「新建,待完善」,之后永不变 —— 界面上是个永久摆设。
    #   · owner:更早的 v4 质感收口(D2)就把展示删了,**生产者却留着** —— 同一个病。
    # 读侧不再生产它们。断言用 assertNotIn 而不是"等于空串":留个空字段等于把坑保温,
    # 下一个人照样会拿它去渲染。**夹具档案里两行字都还在** —— 有内容也不产出,才叫下线干净。
    def test_projects_drops_dead_cockpit_fields(self):
        root = _mkroot({"保利中央公园.md": PROJ_A, "光头项目.md": PROJ_BARE})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        by_key = {p["key"]: p for p in d["projects"]}
        a = by_key["保利中央公园"]
        self.assertIn("- 业主: [[张伟]]", PROJ_A)          # 前提:档案里确实有这两行
        self.assertIn("- 当前状态: 玄关柜待业主确认", PROJ_A)
        self.assertNotIn("owner", a)
        self.assertNotIn("status_note", a)
        bare = by_key["光头项目"]
        self.assertNotIn("owner", bare)
        self.assertNotIn("status_note", bare)

    def test_projects_registered_group_depth2(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_DELIVERED})
        self._add_grouped_workspace(
            root, ["2026/0315 某项目"],
            mapping={"翡翠湾-1801": "2026/0315 某项目"})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        p = {x["key"]: x for x in d["projects"]}["翡翠湾-1801"]
        self.assertFalse(p["unregistered"])
        self.assertEqual(p["group"], "2026")   # 已建档条目也带分组标签

    def test_projects_registered_group_depth1_empty(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_DELIVERED})
        self._add_workspace(root, ["20260601 平湖 翡翠湾 3#1801"])
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects")
        p = {x["key"]: x for x in d["projects"]}["翡翠湾-1801"]
        self.assertEqual(p.get("group", ""), "")  # depth1 恒空,不冒出假分组

    def test_projects_post_405_invariant(self):
        # cockpit 重申:列表端点仍无任何写面
        with _serve(_mkroot({})) as port:
            st, _, _ = _req(port, "/api/projects", method="POST")
        self.assertEqual(st, 405)

    def test_projects_grouped_files_reachable(self):
        # keyed key 含 `:`(wire 上 %3A,路由 unquote 后过闸)经 project_dir
        # 直等绑定,文件区 overview 端到端可用
        root = _mkroot({})
        ws = self._add_grouped_workspace(root, ["2026/0315 某项目"])
        catdir = os.path.join(ws, "2026", "0315 某项目", "02-参考图")
        os.makedirs(catdir, exist_ok=True)
        _write_bytes(os.path.join(catdir, "客厅.png"))
        with _serve(root) as port:
            st, _, d = _get_json(
                port, "/api/files/overview/" + quote("2026:0315 某项目"))
        self.assertEqual(st, 200)
        self.assertTrue(d["configured"] and d["mapped"])
        self.assertEqual(d["categories"][0]["name"], "02-参考图")

    def test_projects_unregistered_files_reachable(self):
        # 未建档 key = 文件夹名(含 #,wire 上 %23)经 project_dir 直等绑定,
        # 文件区 overview 直接可用 —— 字符集闸放宽 # 的端到端凭证
        root = _mkroot({})
        name = "20260701 新签 云璟台 3#301"
        ws = self._add_workspace(root, [name])
        catdir = os.path.join(ws, "01-项目", name, "02-参考图")
        os.makedirs(catdir, exist_ok=True)
        _write_bytes(os.path.join(catdir, "客厅.png"))
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/files/overview/" + quote(name))
        self.assertEqual(st, 200)
        self.assertTrue(d["configured"] and d["mapped"])
        self.assertEqual(d["categories"][0]["name"], "02-参考图")


# ── /api/projects/<key>/changes ──────────────────────────────────────────────
class TestChanges(unittest.TestCase):

    def test_changes_all_statuses(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            st, hd, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/changes")
        self.assertEqual(st, 200)
        self.assertEqual(d["key"], "保利中央公园")
        statuses = [c["status"] for c in d["changes"]]
        self.assertEqual(statuses, ["待确认", "进行中", "已完成", "已关闭", "待确认"])
        c12 = d["changes"][0]
        self.assertEqual(c12["cnum"], 12)
        self.assertEqual(c12["date"], "2026-07-09")
        self.assertIn("玄关柜", c12["text"])
        # space 透传(p4 T1【空间】前缀,parse 单一真相源);无标注行 = None;
        # source 仍无字段 → 恒 None(读侧宽容,accepted deviation)
        self.assertEqual(c12["space"], "玄关")
        self.assertIsNone(d["changes"][1]["space"])
        self.assertIn("source", c12)

    def test_changes_partial_line(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            _, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/changes")
        partial = d["changes"][-1]  # 缺编号缺日期的残缺行
        self.assertEqual(partial["status"], "待确认")
        self.assertEqual(partial["cnum"], None)
        self.assertEqual(partial["date"], None)

    def test_changes_bad_key_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        # 隔壁放一个"不该被读到"的项目文件,逃逸若成立就会命中它
        with open(os.path.join(root, "SECRET.md"), "w", encoding="utf-8") as fh:
            fh.write("# secret")
        bad = ["..", "%2e%2e", "a%2fb", "a%2f%2e%2e%2fSECRET", "%2e%2e%2fSECRET",
               "x%00y", "a%5cb"]
        with _serve(root) as port:
            for k in bad:
                st, _, _ = _req(port, f"/api/projects/{k}/changes")
                self.assertEqual(st, 404, f"key={k!r} 应 404")
            # 空 key(裸双斜线)同 404
            st, _, _ = _req(port, "/api/projects//changes")
            self.assertEqual(st, 404)

    def test_changes_unknown_project_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            st, _, _ = _req(port, "/api/projects/" + quote("不存在的项目") + "/changes")
        self.assertEqual(st, 404)


# ── /api/projects/<key>/changes 历史/备注扩展(track opendesign-todo-edit T3)────
PROJ_HIST = """# 编辑历史项目

- 业主: [[王五]]
- 阶段: 施工图

## 变更记录
- [进行中] C2 2026-06-19 玄关改到顶鞋柜
- [已完成] C5 2026-06-18 【客厅】客厅吊顶改回平顶

## 变更历史
- C2 改于 2026-07-01｜原:玄关改鞋柜
- C2 备注:业主微信确认了
- C5 改于 2026-07-02｜原:客厅吊顶改平顶
- C5 改于 2026-07-03｜原:客厅吊顶改弧形

## 沟通日志
- 2026-07-01 微信

---
最后更新: 2026-07-03
"""


class TestChangesHistory(unittest.TestCase):

    def test_changes_history_and_note_by_cnum(self):
        root = _mkroot({"编辑历史项目.md": PROJ_HIST})
        with _serve(root) as port:
            st, _, d = _get_json(
                port, "/api/projects/" + quote("编辑历史项目") + "/changes")
        self.assertEqual(st, 200)
        self.assertEqual(len(d["changes"]), 2)  # 历史段的行不冒充变更
        by = {c["cnum"]: c for c in d["changes"]}
        # C2:一条留痕 + 备注
        self.assertEqual(by[2]["history"],
                         [{"date": "2026-07-01", "old": "玄关改鞋柜"}])
        self.assertEqual(by[2]["note"], "业主微信确认了")
        self.assertEqual(by[2]["text"], "玄关改到顶鞋柜")  # 主行现值
        # C5:两条留痕按时序,无备注 → 不带 note 键
        self.assertEqual(by[5]["history"],
                         [{"date": "2026-07-02", "old": "客厅吊顶改平顶"},
                          {"date": "2026-07-03", "old": "客厅吊顶改弧形"}])
        self.assertNotIn("note", by[5])
        self.assertEqual(by[5]["space"], "客厅")  # 主行字段照常

    def test_changes_no_history_section_backward_compat(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})
        with _serve(root) as port:
            _, _, d = _get_json(
                port, "/api/projects/" + quote("保利中央公园") + "/changes")
        for c in d["changes"]:  # 无历史段:history 恒空列表,无 note 键
            self.assertEqual(c["history"], [])
            self.assertNotIn("note", c)


# ── POST 写针孔 /api/changes/edit(track opendesign-todo-edit T4,design test 12)──
class TestEditChangePinhole(unittest.TestCase):

    def _root(self):
        return _mkroot({"编辑历史项目.md": PROJ_HIST})

    def _proj_text(self, root):
        with open(os.path.join(root, "projects", "编辑历史项目.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def _post(self, port, path, body, ctype="application/json",
              method="POST", host=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        headers = {}
        if ctype is not None:
            headers["Content-Type"] = ctype
        if host is not None:
            headers["Host"] = host
        data = None
        if body is not None:
            data = body if isinstance(body, (bytes, bytearray)) else \
                json.dumps(body, ensure_ascii=False).encode("utf-8")
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        b = r.read()
        conn.close()
        return r.status, (json.loads(b.decode("utf-8")) if b else None)

    # 正常:改正文 + 加备注 → 200,文件保格式落地 + 留痕 + 备注替换
    def test_edit_happy_path(self):
        root = self._root()
        with _serve(root) as port:
            st, d = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2,
                "new_text": "玄关改嵌入到顶鞋柜", "note": "最终确认"})
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        self.assertEqual(d["cnum"], 2)
        text = self._proj_text(root)
        self.assertIn("- [进行中] C2 2026-06-19 玄关改嵌入到顶鞋柜", text)
        self.assertIn("原:玄关改到顶鞋柜", text)          # 新留痕(旧值)
        self.assertIn("- C2 备注:最终确认", text)          # 备注被替换
        self.assertNotIn("业主微信确认了", text)

    # CT 非 json → 400,文件逐字节不动
    def test_edit_ct_gate_rejects_and_no_write(self):
        root = self._root()
        before = self._proj_text(root)
        with _serve(root) as port:
            st, _ = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2, "new_status": "已完成"},
                ctype="text/plain")
        self.assertEqual(st, 400)
        self.assertEqual(self._proj_text(root), before)

    # body 超限 → 400
    def test_edit_body_too_large(self):
        root = self._root()
        big = (b'{"project":"\xe7\xbc\x96\xe8\xbe\x91\xe5\x8e\x86\xe5\x8f\xb2'
               b'\xe9\xa1\xb9\xe7\x9b\xae","cnum":2,"new_text":"'
               + b'x' * 5000 + b'"}')
        with _serve(root) as port:
            st, _ = self._post(port, "/api/changes/edit", big)
        self.assertEqual(st, 400)

    # 缺 cnum → change_not_found(404)
    def test_edit_missing_cnum(self):
        root = self._root()
        with _serve(root) as port:
            st, d = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "new_status": "已完成"})
        self.assertEqual(st, 404)
        self.assertEqual(d["error"], "change_not_found")

    # 键白名单:夹带 ds_root 走私 → 400,零执行
    def test_edit_extra_key_rejected(self):
        root = self._root()
        before = self._proj_text(root)
        with _serve(root) as port:
            st, _ = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2,
                "new_status": "已完成", "ds_root": "/etc"})
        self.assertEqual(st, 400)
        self.assertEqual(self._proj_text(root), before)

    # 校验类错误:非法 status → 400 invalid_status;空正文 → 400 empty_text
    def test_edit_validation_errors(self):
        root = self._root()
        with _serve(root) as port:
            st1, d1 = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2, "new_status": "done"})
            st2, d2 = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2, "new_text": "   "})
        self.assertEqual((st1, d1["error"]), (400, "invalid_status"))
        self.assertEqual((st2, d2["error"]), (400, "empty_text"))

    # 精确匹配防走私 + 其余未白名单 POST 路径仍 405(不变量),且零副作用
    def test_edit_exact_match_and_405_invariant(self):
        root = self._root()
        before = self._proj_text(root)
        payload = {"project": "编辑历史项目", "cnum": 2, "new_status": "已完成"}
        with _serve(root) as port:
            for p in ("/api/changes/editx", "/api/changes/edit/",
                      "/api/changes/edit/2", "/api/changes", "/api/todos"):
                st, _ = self._post(port, p, payload)
                self.assertEqual(st, 405, f"{p} 应 405")
        self.assertEqual(self._proj_text(root), before)  # 未白名单路径零副作用

    # Host 闸继承:恶意 Host → 403 先于业务逻辑
    def test_edit_host_gate_inherited(self):
        root = self._root()
        with _serve(root) as port:
            st, _ = self._post(port, "/api/changes/edit", {
                "project": "编辑历史项目", "cnum": 2, "new_status": "已完成"},
                host="evil.example")
        self.assertEqual(st, 403)


# ── 真 ds_web 写读闭环(track opendesign-todo-edit T5,design test 13)──────────
class TestEditRoundtrip(unittest.TestCase):
    """起真服务器 → POST 编辑 → GET changes/todos 见新值 + 累积留痕(写读同一真相源)。"""

    def test_roundtrip_edit_then_read(self):
        root = _mkroot({"编辑历史项目.md": PROJ_HIST})
        with _serve(root) as port:
            # POST:C2 改状态→已完成 + 改正文 + 加备注
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request(
                "POST", "/api/changes/edit",
                body=json.dumps({
                    "project": "编辑历史项目", "cnum": 2, "new_status": "已完成",
                    "new_text": "玄关改嵌入到顶鞋柜", "note": "业主拍板"},
                    ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            rb = json.loads(r.read().decode("utf-8"))
            conn.close()
            self.assertEqual(r.status, 200)
            self.assertTrue(rb["ok"])

            # GET changes:新状态 + 新正文 + 备注 + 累积留痕(原有 + 本次)
            _, _, d = _get_json(
                port, "/api/projects/" + quote("编辑历史项目") + "/changes")
            by = {c["cnum"]: c for c in d["changes"]}
            self.assertEqual(by[2]["status"], "已完成")
            self.assertEqual(by[2]["text"], "玄关改嵌入到顶鞋柜")
            self.assertEqual(by[2]["note"], "业主拍板")
            olds = [h["old"] for h in by[2]["history"]]
            self.assertIn("玄关改鞋柜", olds)        # 原留痕保留
            self.assertIn("玄关改到顶鞋柜", olds)    # 本次编辑新增留痕
            # C5 未被本次编辑触碰(隔离)
            self.assertEqual(by[5]["text"], "客厅吊顶改回平顶")

            # GET todos:C2 已完成 → 从未办结列表消失
            _, _, t = _get_json(port, "/api/todos")
            c2_open = [it for it in t["open"]
                       if it["project"] == "编辑历史项目" and it["cnum"] == 2]
            self.assertEqual(c2_open, [])


# ── /api/projects/<key>/refs ─────────────────────────────────────────────────
REFS_INDEX = """# 参考图索引

- [r1] 奶油风|玄关 | 来源:小红书 | 文件:refs/a.jpg | 用于:保利中央公园 | 备注:柜体
- [r2] 侘寂风|客厅 | 来源:Pinterest | 文件:refs/b.png | 用于:翡翠湾-1801 | 备注:
- [r3] 现代简约,轻奢|主卧,衣帽间 | 来源:Behance | 文件:refs/c.webp | 用于:保利中央公园,翡翠湾-1801 | 备注:灯光

---
最后更新: 2026-07-10
"""


class TestRefs(unittest.TestCase):

    def test_refs_filter(self):
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=REFS_INDEX)
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
        self.assertEqual(st, 200)
        ids = {r["id"] for r in d["refs"]}
        self.assertEqual(ids, {"r1", "r3"})  # r2 只用于翡翠湾
        r1 = next(r for r in d["refs"] if r["id"] == "r1")
        self.assertEqual(r1["file"], "refs/a.jpg")
        self.assertIn("奶油风", r1["style"])
        self.assertIn("玄关", r1["space"])
        self.assertEqual(r1["note"], "柜体")

    def test_refs_index_missing_empty(self):
        root = _mkroot({"保利中央公园.md": PROJ_A})  # 无 refs-index.md
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
        self.assertEqual(st, 200)
        self.assertEqual(d["refs"], [])

    def test_refs_bad_key_404(self):
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=REFS_INDEX)
        with _serve(root) as port:
            for k in ("..", "%2e%2e", "a%2fb"):
                st, _, _ = _req(port, f"/api/projects/{k}/refs")
                self.assertEqual(st, 404, f"key={k!r} 应 404")


# ── /api/refs/file/<path> 安全闸(本 track 唯一新增文件读出面) ───────────────
class TestRefsFile(unittest.TestCase):

    def test_file_serve_ok(self):
        root = _mkroot({}, refs_index=REFS_INDEX)
        _write_bytes(os.path.join(root, "refs", "a.jpg"), b"\xff\xd8\xffJPEGDATA")
        with _serve(root) as port:
            st, hd, body = _req(port, "/api/refs/file/a.jpg")
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/jpeg")
        self.assertIn(b"JPEGDATA", body)
        self.assertIn("max-age", hd.get("cache-control", ""))

    def test_file_chinese_name(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "玄关效果图.png"))
        with _serve(root) as port:
            st, hd, _ = _req(port, "/api/refs/file/" + quote("玄关效果图.png"))
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/png")

    def test_file_subdir_ok(self):
        root = _mkroot({})
        os.makedirs(os.path.join(root, "refs", "sub"))
        _write_bytes(os.path.join(root, "refs", "sub", "x.gif"))
        with _serve(root) as port:
            st, hd, _ = _req(port, "/api/refs/file/sub/x.gif")
        self.assertEqual(st, 200)
        self.assertEqual(hd["content-type"], "image/gif")

    # Gate C —— 扩展白名单:refs 内真实非图片文件不得被读出
    def test_file_ext_whitelist(self):
        root = _mkroot({})
        with open(os.path.join(root, "refs", "notes.txt"), "w") as fh:
            fh.write("SECRET-NOTES")
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/notes.txt")
        self.assertEqual(st, 404)
        self.assertNotIn(b"SECRET-NOTES", body)

    # Gate A —— 字符集白名单:含非法字符的路径拒服务(即便真有此文件)
    def test_file_charset_gate(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "bad%x.png"))  # 真实存在
        with _serve(root) as port:
            st, _, _ = _req(port, "/api/refs/file/" + quote("bad%x.png"))
        self.assertEqual(st, 404)  # % 是 URL 编码引信,黑名单 Gate A 拒 → 404,而非 200

    # Gate B —— realpath 前缀:裸 ../ 逃出 refs/ 一律 404 且不泄露内容
    def test_file_traversal(self):
        root = _mkroot({})
        # refs 外(ds_root 下)放一张真图片,逃逸若成立会被读到
        _write_bytes(os.path.join(root, "outer.png"), b"LEAK-OUTER")
        with _serve(root) as port:
            for p in ("/api/refs/file/../outer.png",
                      "/api/refs/file/%2e%2e/outer.png",
                      "/api/refs/file/sub/../../outer.png"):
                st, _, body = _req(port, p)
                self.assertEqual(st, 404, f"{p} -> {st}")
                self.assertNotIn(b"LEAK-OUTER", body)

    # Gate B —— realpath 前缀:refs 内 symlink 指向外部,realpath 展开后必须被拦
    def test_file_symlink_escape(self):
        if not hasattr(os, "symlink"):
            self.skipTest("平台无 symlink")
        root = _mkroot({})
        outer = os.path.join(root, "outer_secret.png")
        _write_bytes(outer, b"LEAK-SYMLINK")
        os.symlink(outer, os.path.join(root, "refs", "escape.png"))
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/escape.png")
        self.assertEqual(st, 404)
        self.assertNotIn(b"LEAK-SYMLINK", body)

    # Gate A 硬化:re 的 $ 在结尾换行前也匹配,\Z 才封死 trailing-newline 变体
    def test_file_trailing_newline_404(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "a.png"))
        with _serve(root) as port:
            st, _, _ = _req(port, "/api/refs/file/a.png%0A")
        self.assertEqual(st, 404)

    def test_file_not_found_no_path_leak(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, _, body = _req(port, "/api/refs/file/nope.png")
        self.assertEqual(st, 404)
        self.assertNotIn(b"nope.png", body)  # 404 不回显路径

    def test_file_write_methods_405(self):
        root = _mkroot({})
        _write_bytes(os.path.join(root, "refs", "a.png"))
        with _serve(root) as port:
            for m in ("POST", "PUT", "DELETE", "PATCH"):
                st, hd, _ = _req(port, "/api/refs/file/a.png", method=m)
                self.assertEqual(st, 405, f"{m} -> {st}")
                self.assertEqual(hd.get("allow"), "GET")


class TestRefsCharsetConvergence(unittest.TestCase):
    """M2(07-13 盲评 + 07-14 v2 黑名单化):refs 列出=可服务同集合。
    Gate A 放行 # / & / 中文全角标点(realpath+within 才是权威闸);只有会破坏路径/URL
    解码的字符(% 等)才拒——那种行既不列出也不服务(诚实缺席)。"""

    IDX = """# 参考图索引

- [r1] 奶油风|玄关 | 来源:小红书 | 文件:refs/12#1802-客厅.jpg | 用于:保利中央公园 | 备注:
- [r2] 侘寂风|客厅 | 来源:小红书 | 文件:refs/坏%图.jpg | 用于:保利中央公园 | 备注:
- [r3] 奶油风|客厅 | 来源:小红书 | 文件:refs/客厅（复尺）&终.jpg | 用于:保利中央公园 | 备注:

---
最后更新: 2026-07-13
"""

    def test_hash_and_punct_row_listed_and_served(self):
        # #(楼栋#户号)与 &/中文全角括号(）——常见真实命名——都必须列得出且服务得到
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=self.IDX)
        for name in ("12#1802-客厅.jpg", "客厅（复尺）&终.jpg"):
            _write_bytes(os.path.join(root, "refs", name), b"\xff\xd8\xffJPEGDATA")
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
            self.assertEqual(st, 200)
            files = [r["file"] for r in d["refs"]]
            for name in ("12#1802-客厅.jpg", "客厅（复尺）&终.jpg"):
                self.assertIn("refs/" + name, files)
                st2, hd, body = _req(port, "/api/refs/file/" + quote(name))
                self.assertEqual(st2, 200, name)
                self.assertIn(b"JPEGDATA", body)

    def test_unservable_row_not_listed(self):
        # % 是 URL 编码引信,黑名单拒 → 既不列出也服务不到(此行诚实缺席)
        root = _mkroot({"保利中央公园.md": PROJ_A}, refs_index=self.IDX)
        with _serve(root) as port:
            st, _, d = _get_json(port, "/api/projects/" + quote("保利中央公园") + "/refs")
        self.assertEqual(st, 200)
        self.assertNotIn("refs/坏%图.jpg", [r["file"] for r in d["refs"]])


# (main 在文件末尾——曾在此处,导致直跑本文件时下方 19 个针孔测试静默不执行,
#  track opendesign-frontend-p1 T0 修正)

# ═══════════════════════════════════════════════════════════════════════════
# track opendesign-clickable-actions — 两个新 POST 写针孔的契约 oracle。
# 主 agent 拥有,执行腿(Sonnet 5)off-limits。二者均是只读墙上的受控开口,
# posture 逐条同 /api/changes/edit:CT json 闸 → body≤OPEN_BODY_MAX → JSON dict
# → 键白名单(多余键即拒,防夹带 ds_root/today 走私)→ 类型闸 → 复用 ds_tools 核心
# → 错误码映射。精确匹配防走私;Host 闸 do_POST 入口继承;trace 不进响应体。
# 核心函数(append_change/create_project)的字段级行为已由 test_ds_tools 覆盖,
# 这里只钉"针孔层"。
# ═══════════════════════════════════════════════════════════════════════════

def _post_json(port, path, body, ctype="application/json", method="POST", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {}
    if ctype is not None:
        headers["Content-Type"] = ctype
    if host is not None:
        headers["Host"] = host
    data = None
    if body is not None:
        data = body if isinstance(body, (bytes, bytearray)) else \
            json.dumps(body, ensure_ascii=False).encode("utf-8")
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    b = r.read()
    conn.close()
    return r.status, (json.loads(b.decode("utf-8")) if b else None)


class TestAddChangePinhole(unittest.TestCase):
    """POST /api/changes/add {project, content, space?} → ds_tools.append_change。"""

    def _root(self):
        return _mkroot({"编辑历史项目.md": PROJ_HIST})

    def _text(self, root):
        with open(os.path.join(root, "projects", "编辑历史项目.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_add_happy_path(self):
        root = self._root()
        with _serve(root) as port:
            st, d = _post_json(port, "/api/changes/add", {
                "project": "编辑历史项目", "content": "主卧飘窗改榻榻米", "space": "主卧"})
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        text = self._text(root)
        # 新行:下一个 cnum(现存 C2/C5 → C6)、状态待确认、带空间前缀
        self.assertIn("[待确认] C6", text)
        self.assertIn("【主卧】主卧飘窗改榻榻米", text)

    def test_add_space_optional(self):
        root = self._root()
        with _serve(root) as port:
            st, d = _post_json(port, "/api/changes/add", {
                "project": "编辑历史项目", "content": "无空间的一条"})
        self.assertEqual(st, 200)
        self.assertIn("C6 ", self._text(root))

    def test_add_ct_gate_rejects_and_no_write(self):
        root = self._root(); before = self._text(root)
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/changes/add",
                               {"project": "编辑历史项目", "content": "x"},
                               ctype="text/plain")
        self.assertEqual(st, 400)
        self.assertEqual(self._text(root), before)

    def test_add_body_too_large(self):
        root = self._root()
        big = (b'{"project":"\xe7\xbc\x96\xe8\xbe\x91\xe5\x8e\x86\xe5\x8f\xb2'
               b'\xe9\xa1\xb9\xe7\x9b\xae","content":"' + b'x' * 5000 + b'"}')
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/changes/add", big)
        self.assertEqual(st, 400)

    def test_add_extra_key_rejected_no_write(self):
        root = self._root(); before = self._text(root)
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/changes/add", {
                "project": "编辑历史项目", "content": "x", "ds_root": "/etc"})
        self.assertEqual(st, 400)
        self.assertEqual(self._text(root), before)

    def test_add_empty_content_400(self):
        root = self._root()
        with _serve(root) as port:
            st, d = _post_json(port, "/api/changes/add", {
                "project": "编辑历史项目", "content": "   "})
        self.assertEqual(st, 400)
        self.assertEqual(d["error"], "empty_content")

    def test_add_project_not_found_404(self):
        root = self._root()
        with _serve(root) as port:
            st, d = _post_json(port, "/api/changes/add", {
                "project": "查无此项目", "content": "x"})
        self.assertEqual(st, 404)
        self.assertEqual(d["error"], "project_not_found")

    def test_add_exact_match_and_405_invariant(self):
        root = self._root(); before = self._text(root)
        payload = {"project": "编辑历史项目", "content": "x"}
        with _serve(root) as port:
            for p in ("/api/changes/addx", "/api/changes/add/", "/api/changes/add/1"):
                st, _ = _post_json(port, p, payload)
                self.assertEqual(st, 405, f"{p} 应 405")
        self.assertEqual(self._text(root), before)

    def test_add_host_gate_inherited(self):
        root = self._root()
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/changes/add",
                               {"project": "编辑历史项目", "content": "x"},
                               host="evil.example")
        self.assertEqual(st, 403)


class TestCreateProjectPinhole(unittest.TestCase):
    """POST /api/projects/create {project, client, stage?, address?} → ds_tools.create_project。"""

    def _exists(self, root, name):
        return os.path.exists(os.path.join(root, "projects", f"{name}.md"))

    def test_create_happy_path(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create", {
                "project": "翠湖天地-1201", "client": "陈先生"})
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        self.assertEqual(d["project"], "翠湖天地-1201")
        self.assertTrue(self._exists(root, "翠湖天地-1201"))

    def test_create_ct_gate_rejects_and_no_write(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/create",
                               {"project": "X-1", "client": "李"}, ctype="text/plain")
        self.assertEqual(st, 400)
        self.assertFalse(self._exists(root, "X-1"))

    def test_create_body_too_large(self):
        root = _mkroot({})
        big = b'{"project":"X","client":"' + b'y' * 5000 + b'"}'
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/create", big)
        self.assertEqual(st, 400)

    def test_create_extra_key_rejected_no_write(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/create", {
                "project": "X-2", "client": "李", "ds_root": "/etc"})
        self.assertEqual(st, 400)
        self.assertFalse(self._exists(root, "X-2"))

    def test_create_without_client_ok(self):
        """track opendesign-intake-simplify(真机反馈 2026-07-24 #3):
        建档表单只填项目名 → body 里根本没有 client 键,必须 200 建成。
        (旧规格断这里 empty_name = 被用户否掉的过时考卷。)"""
        root = _mkroot({})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create", {"project": "X-3"})
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ok"])
        self.assertTrue(self._exists(root, "X-3"))
        with open(os.path.join(root, "projects", "X-3.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("[[]]", text)   # 空链接 = ds_lint 断链陷阱

    def test_create_blank_client_ok(self):
        """client 给空白串(前端旧状态残留/手工调用)同样按"没填"处理,不是 400。"""
        root = _mkroot({})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create",
                               {"project": "X-3b", "client": "  "})
        self.assertEqual(st, 200, d)
        self.assertTrue(self._exists(root, "X-3b"))

    def test_create_empty_project_400(self):
        """项目名仍必填,且被读门 _valid_proj_key 先拦(400 bad request,零落盘)。"""
        root = _mkroot({})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create", {"project": "", "client": "李"})
        self.assertEqual(st, 400)
        self.assertEqual(d["error"], "bad request")

    def test_create_bad_stage_400(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create", {
                "project": "X-4", "client": "李", "stage": "不存在的阶段"})
        self.assertEqual(st, 400)
        self.assertEqual(d["error"], "bad_stage")

    def test_create_duplicate_409(self):
        root = _mkroot({"已有项目.md": PROJ_HIST})
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/create", {
                "project": "已有项目", "client": "李"})
        self.assertEqual(st, 409)
        self.assertEqual(d["error"], "project_exists")

    def test_create_exact_match_and_405_invariant(self):
        root = _mkroot({})
        payload = {"project": "X-9", "client": "李"}
        with _serve(root) as port:
            for p in ("/api/projects/createx", "/api/projects/create/", "/api/projects"):
                st, _ = _post_json(port, p, payload)
                self.assertEqual(st, 405, f"{p} 应 405")
        self.assertFalse(self._exists(root, "X-9"))

    def test_create_rejects_unreadable_name(self):
        # 写门对齐读门:含 .. 的名字(核心 PROJECT_NAME_RE 放行、读侧 _valid_proj_key 拒)
        # 针孔层先拦,不造 GET 恒 404 的项目(subkimi 四审 Low)。
        root = _mkroot({})
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/create", {"project": "a..b", "client": "李"})
        self.assertEqual(st, 400)
        self.assertFalse(self._exists(root, "a..b"))

    def test_create_host_gate_inherited(self):
        root = _mkroot({})
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/create",
                               {"project": "X-5", "client": "李"}, host="evil.example")
        self.assertEqual(st, 403)


# ═══════════════════════════════════════════════════════════════════════════
# track opendesign-frontend-p1 — 写针孔⑨ /api/projects/bind 的契约 oracle。
# 主 agent 拥有,执行腿(Sonnet 5)off-limits。薄壳直调 ds_tools.bind_project
# (名字闸/已发现文件夹两级匹配/原子写全在核心,test_ds_tools 已覆盖字段级行为),
# 这里只钉针孔层:posture + 错误码映射 + 成功写映射。
# ═══════════════════════════════════════════════════════════════════════════

def _mkws(ds_root: str, folders: list[str], depth: int = 1) -> str:
    """临时工作区:01-项目/ 下建 folders(depth=2 时 folders 形如 "2026/夹名"),
    并把 workspace.json 写进 ds_root/config。返回 ws 根。"""
    ws = tempfile.mkdtemp(prefix="ds_web_bind_ws_")
    for f in folders:
        os.makedirs(os.path.join(ws, "01-项目", *f.split("/")))
    cfg = {"root": ws, "projects": {}}
    if depth == 2:
        cfg["projectsDepth"] = 2
    cfg_dir = os.path.join(ds_root, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "workspace.json"), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False)
    return ws


class TestBindProjectPinhole(unittest.TestCase):
    """POST /api/projects/bind {project, folder} → ds_tools.bind_project。"""

    def _ws_map(self, root):
        with open(os.path.join(root, "config", "workspace.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)["projects"]

    def test_bind_happy_path_writes_mapping(self):
        # 项目名与文件夹名对不上(token 也不命中)= 自动三级绑不上的真实场景
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/bind", {
                "project": "翡翠湾-1801", "folder": "老宅翻新项目夹"})
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ok"])
        self.assertEqual(
            self._ws_map(root)["翡翠湾-1801"].replace("\\", "/"),
            "01-项目/老宅翻新项目夹")

    def test_bind_ct_gate_rejects_and_no_write(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/bind",
                               {"project": "翡翠湾-1801", "folder": "老宅翻新项目夹"},
                               ctype="text/plain")
        self.assertEqual(st, 400)
        self.assertEqual(self._ws_map(root), {})

    def test_bind_extra_key_rejected_no_write(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/bind", {
                "project": "翡翠湾-1801", "folder": "老宅翻新项目夹",
                "ds_root": "/etc"})
        self.assertEqual(st, 400)
        self.assertEqual(self._ws_map(root), {})

    def test_bind_non_string_or_empty_rejected(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            for body in ({"project": "", "folder": "老宅翻新项目夹"},
                         {"project": "翡翠湾-1801", "folder": ""},
                         {"project": 3, "folder": "老宅翻新项目夹"},
                         {"project": "翡翠湾-1801", "folder": ["x"]},
                         {"project": "翡翠湾-1801"},
                         {"folder": "老宅翻新项目夹"}):
                st, _ = _post_json(port, "/api/projects/bind", body)
                self.assertEqual(st, 400, body)
        self.assertEqual(self._ws_map(root), {})

    def test_bind_project_not_found_404(self):
        root = _mkroot({})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/bind", {
                "project": "查无此档", "folder": "老宅翻新项目夹"})
        self.assertEqual(st, 404)
        self.assertEqual(d["error"], "project_not_found")

    def test_bind_folder_not_found_404_with_candidates(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/bind", {
                "project": "翡翠湾-1801", "folder": "不存在的夹"})
        self.assertEqual(st, 404)
        self.assertEqual(d["error"], "folder_not_found")
        # 候选名单透传(前端可提示;核心本就回传,针孔不剥)
        self.assertIn("老宅翻新项目夹", d.get("folders", []))

    def test_bind_folder_ambiguous_409(self):
        # depth2:两个分组下同名夹,报纯名 → 撞名不猜
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["2025/同名夹", "2026/同名夹"], depth=2)
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/bind", {
                "project": "翡翠湾-1801", "folder": "同名夹"})
        self.assertEqual(st, 409)
        self.assertEqual(d["error"], "folder_ambiguous")
        self.assertEqual(self._ws_map(root), {})

    def test_bind_workspace_not_configured_409(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})  # 不写 workspace.json
        with _serve(root) as port:
            st, d = _post_json(port, "/api/projects/bind", {
                "project": "翡翠湾-1801", "folder": "老宅翻新项目夹"})
        self.assertEqual(st, 409)
        self.assertEqual(d["error"], "workspace_not_configured")

    def test_bind_exact_match_and_405_invariant(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            for p in ("/api/projects/bindx", "/api/projects/bind/",
                      "/api/projects/bind/1"):
                st, _ = _post_json(port, p, {"project": "x", "folder": "y"})
                self.assertEqual(st, 405, f"{p} 应 405")
        self.assertEqual(self._ws_map(root), {})

    # ── 四审 subkimi L3/L4 补齐 ──────────────────────────────────────────
    def test_bind_body_too_large(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        big = b'{"project":"X","folder":"' + b"y" * 5000 + b'"}'
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/bind", big)
        self.assertEqual(st, 400)
        self.assertEqual(self._ws_map(root), {})

    def test_bind_dotdot_project_rejected(self):
        """写门对齐读门(同 create 针孔):`a..b` 核心 PROJECT_NAME_RE 放行,
        但读侧 _valid_proj_key 拒 → 不许绑出读侧永远寻址不到的映射键。"""
        root = _mkroot({"a..b.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/bind", {
                "project": "a..b", "folder": "老宅翻新项目夹"})
        self.assertEqual(st, 400)
        self.assertEqual(self._ws_map(root), {})

    def test_bind_host_gate_inherited(self):
        root = _mkroot({"翡翠湾-1801.md": PROJ_A})
        _mkws(root, ["老宅翻新项目夹"])
        with _serve(root) as port:
            st, _ = _post_json(port, "/api/projects/bind",
                               {"project": "翡翠湾-1801", "folder": "老宅翻新项目夹"},
                               host="evil.example")
        self.assertEqual(st, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
