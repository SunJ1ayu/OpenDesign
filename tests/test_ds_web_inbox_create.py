#!/usr/bin/env python3
"""track opendesign-chat-image 的 oracle(一)—— 写针孔⑭ `POST /api/inbox/create`。
主 agent 亲写,executor off-limits。

**本服务第一个"建目录"的口**。它存在的唯一理由:0.48.0 缺收件箱时只回一句
"先建一个",把活推回给一个不是程序员的用户。但 `_upload` 的注释同时钉死了
"网页不自己造目录 = 越权",且那条过了四腿评审 —— 所以本口的形状是
**人工点一下才建、只建一层、只建固定名**,不是"上传时顺手建"。判据据此收紧:

1. **只许一层**:父目录必须是工作区根本身。`makedirs` 式的多层、或名字里带路径成分,
   一律拒(c05/c06)。
2. **"已存在"不是错误**:回 `already_exists` 且**不重建** —— 用 `st_ino` 判同一目录,
   不用 mtime(ext4 秒级精度下"重建了但同秒"会假绿,design §oracle 骗过第三条)。
3. **建的名字来自规则表首候选,不硬编码** `00-收件箱`:用户覆盖 taxonomy 后要跟着变
   (c08)—— 否则会建出第二个孤儿收件箱,而列举认的是覆盖后那个。
4. **建完必须"能用"**:判据不是 `isdir`,是 `ds_intake.list_inbox` 立刻认得它
   (c09)。同 test_ds_web_upload 的第 1 条哲学:落盘 ≠ 能用。
5. 每条拒绝路径都断**零副作用**:工作区根下的条目集合不变(c01/c02/c03/c04/c07/c10)。

跑法: python3 -m pytest tests/test_ds_web_inbox_create.py
"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ 自己
import _tmpreg  # noqa: E402  临时目录登记表,见 tests/_tmpreg.py
import ds_intake  # noqa: E402
import ds_taxonomy  # noqa: E402
import ds_web  # noqa: E402

DEFAULT_INBOX = "00-收件箱"      # config/taxonomy.default.json 的 inboxDirs[0]


# ── 夹具 ──────────────────────────────────────────────────────────────────
def _mkds(ws=None, projects=None):
    """建一个 DS_ROOT(+ 可选已存在的工作区);ws=None → 不写 workspace.json。"""
    ds = tempfile.mkdtemp(prefix="inboxc-ds-")
    os.makedirs(os.path.join(ds, "config"), exist_ok=True)
    os.makedirs(os.path.join(ds, "projects"), exist_ok=True)
    if ws is not None:
        with open(os.path.join(ds, "config", "workspace.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"root": ws, "projects": projects or {}}, fh)
    return ds


def _mkws():
    return tempfile.mkdtemp(prefix="inboxc-ws-")


def _mkdist():
    d = _tmpreg.mkdtemp("inboxc-dist-")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(ds_root):
    srv = ds_web.make_server(ds_root, _mkdist(), port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _post(port, path, body, ctype="application/json"):
    """→ (status, json)。连接被提前掐断 → (None, None),照算"被拒"。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": ctype} if ctype else {}
    if body is None:
        data = b""
    elif isinstance(body, (bytes, bytearray)):
        data = body
    else:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        conn.request("POST", path, body=data, headers=headers)
        r = conn.getresponse()
        b = r.read()
        return r.status, (json.loads(b.decode("utf-8")) if b else None)
    except (BrokenPipeError, ConnectionResetError, http.client.RemoteDisconnected):
        return None, None
    finally:
        conn.close()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    conn.request("GET", path)
    r = conn.getresponse()
    b = r.read()
    conn.close()
    return r.status, (json.loads(b.decode("utf-8")) if b else None)


class InboxCreatePinhole(unittest.TestCase):
    """写针孔⑭:POST /api/inbox/create。"""

    def setUp(self):
        self.tmps = []

    def tearDown(self):
        for p in self.tmps:
            shutil.rmtree(p, ignore_errors=True)

    def _env(self, ws=True, projects=None):
        w = _mkws() if ws else None
        ds = _mkds(w, projects)
        self.tmps += [p for p in (ds, w) if p]
        return ds, w

    # ── 闸:请求形状 ───────────────────────────────────────────────────
    def test_c01_non_json_ct_rejected_no_side_effect(self):
        """CSRF 纵深:非 json CT 一律拒(simple content-type 不触发 preflight)。"""
        ds, ws = self._env()
        before = set(os.listdir(ws))
        with _serve(ds) as port:
            st, _ = _post(port, "/api/inbox/create", {}, ctype="text/plain")
        self.assertIn(st, (400, None))
        self.assertEqual(set(os.listdir(ws)), before, "被拒时不许有任何副作用")

    def test_c02_any_body_key_rejected(self):
        """无参可传:键白名单 = 空集。给了键(哪怕是 name)就拒 —— 名字由规则表定,
        不由调用方点名,否则等于"网页可任意建目录"。"""
        ds, ws = self._env()
        before = set(os.listdir(ws))
        with _serve(ds) as port:
            for body in ({"name": "随便"}, {"path": "../x"}, {"x": 1}):
                st, _ = _post(port, "/api/inbox/create", body)
                self.assertIn(st, (400, None), f"应拒:{body}")
        self.assertEqual(set(os.listdir(ws)), before)

    def test_c03_workspace_not_configured(self):
        """没接工作区 → 409,且不许在任何地方造目录。"""
        ds, _ = self._env(ws=False)
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 409)
        self.assertEqual(r.get("error"), "workspace_not_configured")

    def test_c04_bad_taxonomy_degrades_409(self):
        """坏规则表 → taxonomy_bad(与 _upload / list_inbox 同款降级,不崩)。"""
        ds, ws = self._env()
        user_tax = os.path.join(ds, ds_taxonomy.USER_TAXONOMY_REL)
        os.makedirs(os.path.dirname(user_tax), exist_ok=True)
        with open(user_tax, "w", encoding="utf-8") as fh:
            fh.write("{ 坏 json")
        before = set(os.listdir(ws))
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 409)
        self.assertEqual(r.get("error"), "taxonomy_bad")
        self.assertEqual(set(os.listdir(ws)), before)

    # ── 主路径 ────────────────────────────────────────────────────────
    def test_c05_creates_default_inbox_one_level_only(self):
        """四候选全无 → 建出规则表首候选,**父目录就是工作区根**(只一层)。"""
        ds, ws = self._env()
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 200, r)
        self.assertEqual(r.get("inbox"), DEFAULT_INBOX)
        created = os.path.join(ws, DEFAULT_INBOX)
        self.assertTrue(os.path.isdir(created))
        self.assertEqual(os.path.realpath(os.path.dirname(created)),
                         os.path.realpath(ws), "只许在工作区根下建一层")
        # 回显绝对路径:用户点完要知道东西在哪(本单的第一性诉求)
        self.assertEqual(os.path.realpath(r.get("path", "")),
                         os.path.realpath(created))

    def test_c06_does_not_create_nested_dirs(self):
        """收件箱名若被覆盖成多层(a/b),视为坏表拒掉,不许 makedirs 造出中间层。"""
        ds, ws = self._env()
        user_tax = os.path.join(ds, ds_taxonomy.USER_TAXONOMY_REL)
        os.makedirs(os.path.dirname(user_tax), exist_ok=True)
        with open(user_tax, "w", encoding="utf-8") as fh:
            json.dump({"inboxDirs": ["深/收件箱"]}, fh, ensure_ascii=False)
        before = set(os.listdir(ws))
        with _serve(ds) as port:
            st, _ = _post(port, "/api/inbox/create", {})
        self.assertIn(st, (400, 409), "多层候选不许建")
        self.assertEqual(set(os.listdir(ws)), before)
        self.assertFalse(os.path.exists(os.path.join(ws, "深")))

    def test_c07_already_exists_is_not_an_error_and_does_not_rebuild(self):
        """已有收件箱 → already_exists;**同一个 inode**(不是"看着还在")。
        用 st_ino 而非 mtime:ext4 秒级精度下"删了重建但同秒"会假绿。"""
        ds, ws = self._env()
        inbox = os.path.join(ws, DEFAULT_INBOX)
        os.makedirs(inbox)
        with open(os.path.join(inbox, "旧图.png"), "wb") as fh:
            fh.write(b"x")
        ino_before = os.stat(inbox).st_ino
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 200, r)
        self.assertEqual(r.get("status"), "already_exists")
        self.assertEqual(os.stat(inbox).st_ino, ino_before, "不许重建")
        self.assertTrue(os.path.exists(os.path.join(inbox, "旧图.png")),
                        "里面的文件一根头发都不许动")

    def test_c08_honours_user_taxonomy_first_candidate(self):
        """用户覆盖首候选 → 建的是覆盖后的名字。硬编码 00-收件箱 会建出孤儿目录:
        列举认的是覆盖后那个,用户传的图从此看不见。"""
        ds, ws = self._env()
        user_tax = os.path.join(ds, ds_taxonomy.USER_TAXONOMY_REL)
        os.makedirs(os.path.dirname(user_tax), exist_ok=True)
        with open(user_tax, "w", encoding="utf-8") as fh:
            json.dump({"inboxDirs": ["收件箱"]}, fh, ensure_ascii=False)
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 200, r)
        self.assertEqual(r.get("inbox"), "收件箱")
        self.assertTrue(os.path.isdir(os.path.join(ws, "收件箱")))
        self.assertFalse(os.path.exists(os.path.join(ws, DEFAULT_INBOX)),
                         "不许无视覆盖去建默认名")

    def test_c09_created_inbox_is_immediately_usable(self):
        """主判据:建完 `list_inbox` 立刻认得(configured:true)。
        `isdir` 为真但列举不认 = 用户在界面上永远看不到它 —— 落盘≠能用。"""
        ds, ws = self._env()
        with _serve(ds) as port:
            st, _ = _post(port, "/api/inbox/create", {})
            self.assertEqual(st, 200)
            st2, r2 = _get(port, "/api/intake")
        self.assertEqual(st2, 200)
        self.assertTrue(r2.get("configured"), r2)
        self.assertEqual(r2.get("inbox"), DEFAULT_INBOX)
        r3 = ds_intake.list_inbox(ds)
        self.assertTrue(r3.get("ok"), r3)

    def test_c10_name_taken_by_a_file(self):
        """根下已有同名**文件**(不是目录)→ name_taken,不覆盖、不删。"""
        ds, ws = self._env()
        clash = os.path.join(ws, DEFAULT_INBOX)
        with open(clash, "wb") as fh:
            fh.write("我是文件不是目录".encode("utf-8"))
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 409)
        self.assertEqual(r.get("error"), "name_taken")
        self.assertTrue(os.path.isfile(clash), "原文件必须原封不动")
        with open(clash, "rb") as fh:
            self.assertEqual(fh.read(), "我是文件不是目录".encode("utf-8"))

    def test_c11_symlinked_candidate_not_followed(self):
        """根下已有同名**符号链接指向工作区外** → 不许当"已存在"接受,
        也不许顺着它往外写。(worktree 符号链接事故的同源教训:链接不是目录。)"""
        ds, ws = self._env()
        outside = tempfile.mkdtemp(prefix="inboxc-outside-")
        self.tmps.append(outside)
        os.symlink(outside, os.path.join(ws, DEFAULT_INBOX))
        with _serve(ds) as port:
            st, r = _post(port, "/api/inbox/create", {})
        self.assertEqual(st, 409, r)
        self.assertIn(r.get("error"), ("name_taken", "inbox_outside_root"))
        self.assertEqual(os.listdir(outside), [], "不许往链接指向的外部目录写任何东西")

    def test_c12_get_intake_tells_where_it_would_be_created(self):
        """没收件箱时,`/api/intake` 要回**将要建在哪** —— 按钮才能在点之前
        把路径写在提示里(用户按下去之前就知道会发生什么)。"""
        ds, ws = self._env()
        with _serve(ds) as port:
            st, r = _get(port, "/api/intake")
        self.assertEqual(st, 200)
        self.assertFalse(r.get("configured"))
        self.assertEqual(r.get("reason"), "inbox_not_found")
        self.assertEqual(os.path.realpath(r.get("wouldCreate", "")),
                         os.path.realpath(os.path.join(ws, DEFAULT_INBOX)))

    def test_c13_intake_shows_inbox_path_but_mcp_tool_does_not(self):
        """网页要显示绝对路径(`/api/intake.path`),但 `ds_intake.list_inbox`
        —— 同时是 MCP 工具 —— **不许**带绝对路径:那等于把本机路径喂给 LLM 并上云
        (ds_tools.py:542 铁律)。网页要显示 ≠ 模型要知道。"""
        ds, ws = self._env()
        os.makedirs(os.path.join(ws, DEFAULT_INBOX))
        with _serve(ds) as port:
            st, r = _get(port, "/api/intake")
        self.assertEqual(st, 200)
        self.assertEqual(os.path.realpath(r.get("path", "")),
                         os.path.realpath(os.path.join(ws, DEFAULT_INBOX)))
        tool = ds_intake.list_inbox(ds)
        flat = json.dumps(tool, ensure_ascii=False)
        self.assertNotIn(ws, flat, "MCP 工具返回里不许出现工作区绝对路径")


if __name__ == "__main__":
    unittest.main()


class EnsureInboxDir(unittest.TestCase):
    """建目录那一步单独可测(修复轮):
    - F1(subdeepseek/subglm 独立提出):候选名是 Windows 保留设备名 → 要在建之前
      就拒,给明确的 bad_inbox_name;真机上 `mkdir CON` 的表现无法在 Linux 上验,
      但"提前拒"这件事与平台无关 → 真绿。
    - F3(subdeepseek):**连点两次「帮我建收件箱」**。第二个请求在 lexists 之后、
      mkdir 之前那一瞬被第一个抢先建成 → mkdir 抛 FileExistsError,0.49.0 会回
      409 name_taken(人话是"根目录下有个同名文件") = **对用户撒谎**。
      竞态本身不好在 HTTP 层复现,所以判据打**竞态之后的状态**:目录已存在时调
      同一个内部助手,必须回 already_exists 而不是报错。
    """

    def setUp(self):
        self.ws = _mkws()
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_c14_windows_reserved_candidate_rejected_before_mkdir(self):
        for name in ["CON", "nul", "com1", "PRN.收件箱"]:
            before = set(os.listdir(self.ws))
            status, err = ds_web._ensure_inbox_dir(self.ws, name)
            self.assertIsNone(status, f"{name} 应该在建之前就被拒")
            self.assertEqual(err, "bad_inbox_name")
            self.assertEqual(set(os.listdir(self.ws)), before, "被拒时零副作用")

    def test_c15_race_lost_reports_already_exists_not_name_taken(self):
        """竞态输了(别人先建成)≠ 名字被文件占;不能对用户撒谎。"""
        os.mkdir(os.path.join(self.ws, DEFAULT_INBOX))
        status, err = ds_web._ensure_inbox_dir(self.ws, DEFAULT_INBOX)
        self.assertIsNone(err, f"目录已存在不是错误:{err}")
        self.assertEqual(status, "already_exists")

    def test_c16_real_file_in_the_way_still_name_taken(self):
        """真的是文件占名 → 仍要 name_taken(别把 c15 的修法用成"一律 already_exists")。"""
        with open(os.path.join(self.ws, DEFAULT_INBOX), "wb") as fh:
            fh.write(b"file")
        status, err = ds_web._ensure_inbox_dir(self.ws, DEFAULT_INBOX)
        self.assertIsNone(status)
        self.assertEqual(err, "name_taken")

    def test_c17_symlink_in_the_way_never_followed(self):
        outside = tempfile.mkdtemp(prefix="inboxc-out2-")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        os.symlink(outside, os.path.join(self.ws, DEFAULT_INBOX))
        status, err = ds_web._ensure_inbox_dir(self.ws, DEFAULT_INBOX)
        self.assertIsNone(status)
        self.assertIn(err, ("name_taken", "inbox_outside_root"))
        self.assertEqual(os.listdir(outside), [], "不许顺着链接往外写")

    def test_c18_happy_path_creates_one_level(self):
        status, err = ds_web._ensure_inbox_dir(self.ws, DEFAULT_INBOX)
        self.assertIsNone(err)
        self.assertEqual(status, "created")
        p = os.path.join(self.ws, DEFAULT_INBOX)
        self.assertTrue(os.path.isdir(p))
        self.assertEqual(os.path.realpath(os.path.dirname(p)), os.path.realpath(self.ws))
