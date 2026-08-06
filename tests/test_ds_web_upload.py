#!/usr/bin/env python3
"""track opendesign-image-upload 的 oracle —— 网页拖拽上传图片进收件箱。
主 agent 亲写,executor off-limits。

**本仓第一个"网页给字节、服务端落盘"的口**,所以判据比别处狠:

1. **主判据不是"文件落盘了",是"`GET /api/intake` 里看得见它"**。
   只断 `os.listdir` 会漏掉最阴的一类坑:名字含 `%` 的文件落盘成功,但收件箱列举
   (`ds_intake.py:177` 用 `ds_workspace._SEG_RE` 过滤)永远跳过它 → 用户在界面上
   看不见、扫描整理也搬不动,只能自己去文件夹里翻。落盘 ≠ 能用。
2. **每条拒绝路径都断"零写盘"**(收件箱里文件数不变、无 `.upload-*.tmp` 残留)。
3. 名字闸做成纯函数 + 表驱动:这些用例断的是"闸有没有拒",与平台无关 → **真绿**。
   真正跑不了的是"Windows 上冒号会不会造 ADS、CON 会不会写到设备、尾点会不会被剥"
   —— 那些进 verify.md 的 UNTESTED 清单,本文件不假装能验。

跑法: python3 -m pytest tests/test_ds_web_upload.py
"""
import base64
import http.client
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_web  # noqa: E402


# ── 夹具:一张真 PNG(不是占位字节 —— 上传口以后若加魔数校验,占位字节会假红)──
def png_bytes(w=8, h=8, rgb=(200, 120, 60)):
    rows = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t, d):
        return (struct.pack(">I", len(d)) + t + d
                + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def data_url(blob=None, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(
        png_bytes() if blob is None else blob).decode()


def _mkroot_with_inbox(inbox_name="00-收件箱"):
    """建一个带工作区 + 收件箱的临时 DS_ROOT。"""
    ds = tempfile.mkdtemp(prefix="upload-ds-")
    ws = tempfile.mkdtemp(prefix="upload-ws-")
    os.makedirs(os.path.join(ds, "projects"), exist_ok=True)
    os.makedirs(os.path.join(ds, "config"), exist_ok=True)
    if inbox_name:
        os.makedirs(os.path.join(ws, inbox_name), exist_ok=True)
    with open(os.path.join(ds, "config", "workspace.json"), "w", encoding="utf-8") as fh:
        json.dump({"root": ws, "projects": {}}, fh)
    return ds, ws


def _mkdist():
    d = tempfile.mkdtemp(prefix="upload-dist-")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(ds_root):
    srv = ds_web.make_server(ds_root, _mkdist(), port=0)   # 与 test_ds_web_api 同款起法
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _post(port, path, body, ctype="application/json"):
    """返回 (status, json)。**连接被服务端提前掐断 → (None, None)**:
    体积闸是在读 body **之前**判的(正确姿态:不能先收 20MB 再说不要),于是客户端
    还在发、服务端已经关,http.client 抛 BrokenPipe/ConnectionReset。那也是一种
    "被拒绝",判据照收 —— 但零写盘那条断言仍然要过。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": ctype} if ctype else {}
    data = body if isinstance(body, (bytes, bytearray)) else \
        json.dumps(body, ensure_ascii=False).encode("utf-8")
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


class SafeUploadName(unittest.TestCase):
    """名字闸(纯函数,表驱动)。断的是"拒不拒",与操作系统无关 —— 真绿。"""

    def ok(self, name):
        got = ds_web._safe_upload_name(name)
        self.assertIsNotNone(got, f"应放行:{name!r}")
        return got

    def rejected(self, name, why):
        self.assertIsNone(ds_web._safe_upload_name(name), f"应拒绝({why}):{name!r}")

    def test_n01_plain_names_pass(self):
        for n in ["客厅.png", "现场照片 01.jpg", "翡翠湾-1801 主卧 (2).jpeg",
                  "sofa.webp", "动图.gif"]:
            self.assertEqual(self.ok(n), n)

    def test_n02_percent_rejected(self):
        """`%` 不是安全问题,是**功能黑洞**:落盘成功但收件箱列举(_SEG_RE)永远跳过它。"""
        self.rejected("70%完成.png", "_SEG_RE 禁 %,收件箱列举会跳过")

    def test_n03_path_separators_and_traversal(self):
        for n in ["../evil.png", "..\\evil.png", "a/b.png", "a\\b.png", "..", "."]:
            self.rejected(n, "路径成分/遍历")

    def test_n04_colon_rejected_ads_surface(self):
        """NTFS 备用数据流:`evil.exe:x.png` 过扩展名闸,Windows 上却会造出 evil.exe。"""
        self.rejected("evil.exe:x.png", "NTFS ADS 面")

    def test_n05_leading_dot_rejected(self):
        """点号开头的文件收件箱列举会跳过(ds_intake.py:177)→ 传了也看不见。"""
        self.rejected(".隐藏.png", "收件箱列举跳过点号开头")

    def test_n06_trailing_dot_or_space_rejected(self):
        for n in ["客厅.png.", "客厅.png "]:
            self.rejected(n, "Windows 静默剥尾点/尾空格 → 名字对不上")

    def test_n07_windows_reserved_rejected(self):
        for n in ["CON.png", "con.png", "NUL.png", "COM1.png", "LPT9.png", "AUX.png"]:
            self.rejected(n, "Windows 保留设备名")

    def test_n08_control_chars_rejected(self):
        self.rejected("客厅\x01.png", "控制符")
        self.rejected("客厅\n.png", "换行")

    def test_n09_empty_and_extless(self):
        for n in ["", "   ", "没有扩展名"]:
            self.rejected(n, "空/无扩展名")

    def test_n10_long_name_is_truncated_not_rejected(self):
        """超长名不拒、截短(Windows 260 全路径预算)。炸在 apply_plan 移动那步的话,
        用户看到的是"确认执行失败"而不是"名字太长"。"""
        long_name = "客" * 300 + ".png"
        got = self.ok(long_name)
        self.assertTrue(got.endswith(".png"))
        self.assertLessEqual(len(got), 100, f"应截短,实测 {len(got)}")

    def test_n11_extension_whitelist(self):
        # 2026-08-06(track inbox-accepts-docs):白名单从"只收图片"扩到"分类表认识的格式",
        # 所以 .dwg/.pdf **从这条移到 d02 正面问**(它们现在该收)。
        # 这条留下的是**仍然不收**的那些 —— 断言一条没弱:
        #   svg = 可直开的脚本载体;exe = 可执行;zip = 分类表不认识、且是套娃载体。
        for n in ["脚本.svg", "程序.exe", "存档.zip", "批处理.bat", "快捷方式.lnk"]:
            self.rejected(n, "扩展名不在上传口白名单")
        for n in ["图纸.dwg", "文档.pdf"]:
            self.assertIsNotNone(ds_web._safe_upload_name(n),
                                 f"分类表认识的格式现在应当放行:{n}")

    def test_n12_directory_component_is_rejected_not_rewritten(self):
        """带目录成分的名字**直接拒**,不做 basename 改写 —— 悄悄把 `C:\\...\\evil.png`
        洗成 `evil.png` 会把"对方想干什么"这条信息抹掉(四审 subdeepseek 提的注释失真:
        原注释写"只取末段",与实现不符)。""" 
        self.assertIsNone(ds_web._safe_upload_name("C:\\Windows\\System32\\evil.png"))


class UploadEndpoint(unittest.TestCase):
    """端点闸序 + 落盘语义。主判据走 /api/intake,不走 os.listdir。"""

    def setUp(self):
        self.ds, self.ws = _mkroot_with_inbox()
        self.inbox = os.path.join(self.ws, "00-收件箱")
        self.addCleanup(shutil.rmtree, self.ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def inbox_files(self):
        return sorted(os.listdir(self.inbox))

    def intake_names(self, port):
        st, d = _get(port, "/api/intake")
        self.assertEqual(st, 200, d)
        return sorted(e.get("name") for e in (d.get("entries") or []))

    # ── happy path:主判据 = 收件箱界面里看得见 ──────────────────────────────
    def test_u01_upload_lands_and_is_visible_in_intake(self):
        with _serve(self.ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "客厅现场.png", "data_url": data_url()})
            self.assertEqual(st, 200, d)
            self.assertTrue(d.get("ok"))
            self.assertEqual(d.get("name"), "客厅现场.png")   # 回显真实落盘名
            # ⚠️ 关键:不是 listdir,是"整理链路看得见"
            self.assertIn("客厅现场.png", self.intake_names(port))
        with open(os.path.join(self.inbox, "客厅现场.png"), "rb") as fh:
            self.assertEqual(fh.read(), png_bytes())          # 字节原样,没被改写

    # ── 撞名不覆盖 ──────────────────────────────────────────────────────────
    def test_u02_collision_does_not_overwrite(self):
        other = png_bytes(rgb=(1, 2, 3))
        with _serve(self.ds) as port:
            _post(port, "/api/upload", {"name": "客厅.png", "data_url": data_url()})
            st, d = _post(port, "/api/upload",
                          {"name": "客厅.png", "data_url": data_url(other)})
            self.assertEqual(st, 200, d)
            self.assertNotEqual(d["name"], "客厅.png", "撞名必须换名,不能覆盖")
            names = self.intake_names(port)
        self.assertIn("客厅.png", names)
        self.assertIn(d["name"], names)
        with open(os.path.join(self.inbox, "客厅.png"), "rb") as fh:
            self.assertEqual(fh.read(), png_bytes(), "第一张的字节必须原封不动")

    # ── 拒绝路径:每条都零写盘 ──────────────────────────────────────────────
    def _reject(self, port, body, ctype="application/json", expect=400):
        before = self.inbox_files()
        st, _d = _post(port, "/api/upload", body, ctype=ctype)
        self.assertIn(st, (expect, None))   # None = 服务端在读 body 前就掐断(见 _post)
        self.assertEqual(self.inbox_files(), before, "拒绝路径必须零写盘")

    def test_u03_ct_gate(self):
        with _serve(self.ds) as port:
            self._reject(port, {"name": "a.png", "data_url": data_url()},
                         ctype="text/plain")

    def test_u04_extra_key_rejected(self):
        with _serve(self.ds) as port:
            self._reject(port, {"name": "a.png", "data_url": data_url(),
                                "dest": "/etc"})

    def test_u05_non_str_types(self):
        with _serve(self.ds) as port:
            self._reject(port, {"name": 1, "data_url": data_url()})
            self._reject(port, {"name": "a.png", "data_url": 2})

    def test_u06_bad_name_rejected(self):
        with _serve(self.ds) as port:
            for n in ["../evil.png", "70%完成.png", "CON.png", ".x.png", "x.svg"]:
                self._reject(port, {"name": n, "data_url": data_url()})

    def test_u07_mime_must_match_extension(self):
        """名叫 .png、data URL 却声明 image/gif → 拒(防"名实不符")。"""
        with _serve(self.ds) as port:
            self._reject(port, {"name": "a.png",
                                "data_url": data_url(mime="image/gif")})
            self._reject(port, {"name": "a.png",
                                "data_url": data_url(mime="text/html")})

    def test_u08_bad_base64(self):
        with _serve(self.ds) as port:
            self._reject(port, {"name": "a.png", "data_url": "data:image/png;base64,@@@@"})
            self._reject(port, {"name": "a.png", "data_url": "not-a-data-url"})

    def test_u09_body_too_large(self):
        """体积闸在读 body 之前(Content-Length),不能先收 100MB 再判。"""
        big = b'{"name":"a.png","data_url":"' + b"A" * (20 * 1024 * 1024) + b'"}'
        with _serve(self.ds) as port:
            self._reject(port, big)

    def test_u10_decoded_bytes_too_large(self):
        """体积在信封内但解码后超 8MB → 拒(base64 膨胀 4/3,信封闸拦不住这条)。"""
        with _serve(self.ds) as port:
            blob = b"\x89PNG\r\n\x1a\n" + b"x" * (9 * 1024 * 1024)
            self._reject(port, {"name": "a.png", "data_url": data_url(blob)})

    def test_u11_no_temp_file_left_behind(self):
        """失败之后不能留 `.upload-*.tmp`:半截文件会被「扫描整理」当正常文件归档。"""
        with _serve(self.ds) as port:
            _post(port, "/api/upload", {"name": "x.svg", "data_url": data_url()})
            _post(port, "/api/upload", {"name": "a.png", "data_url": "data:image/png;base64,@@"})
        self.assertEqual([f for f in os.listdir(self.inbox) if f.startswith(".upload-")], [])

    def test_u12_method_and_path_are_exact(self):
        """GET /api/upload 不该是写口;前缀路径不得走私。"""
        with _serve(self.ds) as port:
            st, _ = _get(port, "/api/upload")
            self.assertIn(st, (404, 405))
            st2, _ = _post(port, "/api/upload/../etc",
                           {"name": "a.png", "data_url": data_url()})
            self.assertIn(st2, (400, 404, 405))


class UploadWithoutInbox(unittest.TestCase):
    """没有收件箱目录时:409 人话错误,零写盘,不自己造目录
    (造目录 = 网页在用户工作区里凭空建文件夹,越权)。"""

    def test_u13_inbox_not_found(self):
        ds, ws = _mkroot_with_inbox(inbox_name=None)
        self.addCleanup(shutil.rmtree, ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        with _serve(ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "a.png", "data_url": data_url()})
        self.assertEqual(st, 409, d)
        self.assertEqual(d.get("error"), "inbox_not_found")
        self.assertEqual(os.listdir(ws), [], "不许自己造收件箱目录")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ══════════════════════════════════════════════════════════════════════════
# 四审修复轮(2026-07-26):subkimi F1/F4 + subdeepseek 的注释失真。
# F1 是真缺陷:`ds_taxonomy.load_taxonomy` 坏表返回 None,而 `_find_inbox(cfg, None)`
# 会 `taxonomy["inboxDirs"]` 抛 TypeError —— 兄弟端点(list_inbox/stage)都优雅降级成
# `taxonomy_bad` → 409,只有这个新口会**连响应都不给**(浏览器看到 Failed to fetch)。
# F4 是错误码语义:体积超限走的是通用 `bad request`,前端于是显示"上传失败(bad request)";
# svg 因 mime 以 image/ 开头能过前端过滤,到服务端却被判 bad_name → 提示"改个名再试"=错药方。
# ══════════════════════════════════════════════════════════════════════════


class DegradesInsteadOfCrashing(unittest.TestCase):
    """坏 taxonomy → 409 taxonomy_bad(与兄弟端点同款),不是断连接。"""

    def test_u14_bad_taxonomy_degrades(self):
        ds, ws = _mkroot_with_inbox()
        self.addCleanup(shutil.rmtree, ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        # 用户覆盖表写成坏 JSON → load_taxonomy 返回 None
        with open(os.path.join(ds, "config", "taxonomy.json"), "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")
        with _serve(ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "a.png", "data_url": data_url()})
        self.assertEqual(st, 409, d)          # 不是 None(断连)、不是 500
        self.assertEqual(d.get("error"), "taxonomy_bad")
        self.assertEqual(os.listdir(os.path.join(ws, "00-收件箱")), [], "零写盘")


class ErrorCodesAreActionable(unittest.TestCase):
    """错误码要能翻译成对的人话 —— 前端 uploadErrMsg 按码给建议,码不对 = 建议不对。"""

    def setUp(self):
        self.ds, self.ws = _mkroot_with_inbox()
        self.addCleanup(shutil.rmtree, self.ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_u15_oversize_says_too_large_not_bad_request(self):
        """信封超上限:要给"太大"这一族的码,而不是通用 bad request。
        (2026-08-06:上限随文档上传从 14MB 抬到 44MB,夹具跟着声称 60MB。)

        ⚠️ 夹具讲究:真发 20MB 会被服务端在读 body 前掐断 → 客户端 BrokenPipe →
        断言变成空跑(第一版就是这样,自欺)。改成**声称 20MB、只发几个字节**:
        体积闸看的是 Content-Length,于是能干净地收到响应。"""
        with _serve(self.ds) as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
            conn.putrequest("POST", "/api/upload")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(60 * 1024 * 1024))
            conn.endheaders()
            conn.send(b'{"name":')          # 只发一点点,不发完
            r = conn.getresponse()
            body = r.read()
            st, d = r.status, (json.loads(body.decode("utf-8")) if body else None)
            conn.close()
        self.assertEqual(st, 413, d)
        self.assertEqual((d or {}).get("error"), "too_large")

    def test_u16_wrong_type_says_bad_type_not_bad_name(self):
        """svg/bmp 这类"是图但不收"的:码要说"类型不收",不能说"名字不行"
        —— 前端按 bad_name 会建议"改个名再试",而改名根本没用。"""
        with _serve(self.ds) as port:
            for n in ["脚本.svg", "位图.bmp", "存档.zip"]:   # dwg 已改为收(见 d02)
                st, d = _post(port, "/api/upload",
                              {"name": n, "data_url": data_url()})
                self.assertEqual(st, 400, d)
                self.assertEqual((d or {}).get("error"), "bad_type", n)

    def test_u17_bad_name_still_says_bad_name(self):
        """真·名字问题仍然回 bad_name(别把两类混成一个码)。"""
        with _serve(self.ds) as port:
            for n in ["../evil.png", "70%完成.png", "CON.png"]:
                st, d = _post(port, "/api/upload",
                              {"name": n, "data_url": data_url()})
                self.assertEqual(st, 400, d)
                self.assertEqual((d or {}).get("error"), "bad_name", n)


class ResponseHardening(unittest.TestCase):
    """subkimi F5:nosniff 加了却没判据 —— 补上(它现在是全服务级承诺)。"""

    def test_u18_nosniff_header_present(self):
        ds, ws = _mkroot_with_inbox()
        self.addCleanup(shutil.rmtree, ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        with _serve(ds) as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
            conn.request("GET", "/api/health")
            r = conn.getresponse()
            r.read()
            hd = {k.lower(): v for k, v in r.getheaders()}
            conn.close()
        self.assertEqual(hd.get("x-content-type-options"), "nosniff")

    # ── track opendesign-chat-image 追加:"东西去哪了" ─────────────────────
    # 用户原话:「收件箱是在我电脑哪个文件夹」—— 他被迫来问人,就是提示不合格。
    # 0.48.0 只回 name/inbox,前端只能说"已存进收件箱";这两条要求回**绝对路径**。
    def test_u19_response_carries_absolute_path(self):
        ds, ws = _mkroot_with_inbox()
        self.addCleanup(shutil.rmtree, ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        with _serve(ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "落点.png", "data_url": data_url()})
        self.assertEqual(st, 200, d)
        p = d.get("path")
        self.assertTrue(isinstance(p, str) and os.path.isabs(p), f"要绝对路径:{p!r}")
        self.assertTrue(os.path.isfile(p), "回的路径必须真指向刚落盘的那个文件")
        # 与 name/inbox 三者自洽:路径末段 = 真实落盘名,父目录 = 收件箱
        self.assertEqual(os.path.basename(p), d["name"])
        self.assertEqual(os.path.realpath(os.path.dirname(p)),
                         os.path.realpath(os.path.join(ws, d["inbox"])))

    def test_u20_path_stays_inside_inbox_on_collision_rename(self):
        """撞名换名后 path 仍须指向收件箱内那个新名字(别回旧名的路径)。"""
        ds, ws = _mkroot_with_inbox()
        self.addCleanup(shutil.rmtree, ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        inbox = os.path.join(ws, "00-收件箱")
        with _serve(ds) as port:
            _post(port, "/api/upload", {"name": "撞.png", "data_url": data_url()})
            st, d = _post(port, "/api/upload",
                          {"name": "撞.png", "data_url": data_url(png_bytes(rgb=(9, 9, 9)))})
        self.assertEqual(st, 200, d)
        self.assertNotEqual(d["name"], "撞.png")
        self.assertEqual(os.path.basename(d["path"]), d["name"])
        self.assertEqual(os.path.realpath(os.path.dirname(d["path"])),
                         os.path.realpath(inbox))


# ── track inbox-accepts-docs(2026-08-06):收件箱不再只收图片 ──────────────────
# 用户原话:「收件箱肯定要覆盖别的格式的 **特别是 pdf 和 dwg**」。
# 分类表(config/taxonomy.default.json)**早就给这些格式定好了归宿**,堵的只有入口。
# 放宽写口 = 安全面,所以这组判据盯三件事:
#   ① 白名单与分类表**不许漂移**(以后加了格式却忘了开入口 / 反之,当场红);
#   ② 收不收**看内容签名不看 mime** —— 浏览器给 .dwg 的 mime 常是空或 octet-stream,
#      拿 mime 当判据等于没判;把 PNG 改名成 .pdf 必须拒;
#   ③ 每条拒绝路径照旧**零写盘**。
PDF_BYTES = b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
DWG_BYTES = b"AC1032" + b"\x00" * 64          # 真 DWG 头:AC10xx 版本号
DXF_BYTES = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF\n"
OOXML_BYTES = b"PK\x03\x04" + b"\x00" * 64   # docx/xlsx/pptx 都是 zip
OLE_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64  # 老 doc/xls/max
PSD_BYTES = b"8BPS" + b"\x00" * 64
SKP_BYTES = b"\xff\xfeS\x00k\x00e\x00t\x00c\x00h\x00U\x00p\x00" + b"\x00" * 32


def raw_data_url(blob: bytes, mime: str = "application/octet-stream") -> str:
    return "data:" + mime + ";base64," + base64.b64encode(blob).decode("ascii")


class InboxAcceptsDocs(unittest.TestCase):
    """收件箱收 PDF/DWG 等格式(track inbox-accepts-docs)。"""

    def setUp(self):
        self.ds, self.ws = _mkroot_with_inbox()
        self.inbox = os.path.join(self.ws, "00-收件箱")
        self.addCleanup(shutil.rmtree, self.ds, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def inbox_files(self):
        return sorted(os.listdir(self.inbox))

    def intake_names(self, port):
        st, d = _get(port, "/api/intake")
        self.assertEqual(st, 200, d)
        return sorted(e.get("name") for e in (d.get("entries") or []))

    # ① 入口白名单 ↔ 分类表:两边任一漂移就红
    def test_d01_whitelist_matches_default_taxonomy(self):
        tax = json.load(open(os.path.join(ROOT, "config", "taxonomy.default.json"),
                             encoding="utf-8"))
        want = {e.lower() for c in tax["categories"] for e in c["extensions"]}
        got = set(ds_web._INBOX_UPLOAD)
        self.assertEqual(got, want,
                         "上传口白名单与默认分类表漂移了:"
                         f"分类表有而入口没有={sorted(want - got)};"
                         f"入口有而分类表没有={sorted(got - want)}")

    # ② 真文件收得下,而且**收件箱界面里看得见**(落盘 ≠ 能用)
    def test_d02_real_docs_land_and_are_visible(self):
        cases = [
            ("平面图.pdf", PDF_BYTES, "application/pdf"),
            ("平面图.dwg", DWG_BYTES, "application/octet-stream"),   # 浏览器常给这个
            ("平面图.dxf", DXF_BYTES, ""),                            # 也常常什么都不给
            ("清单.xlsx", OOXML_BYTES, ""),
            ("说明.doc", OLE_BYTES, ""),
            ("贴图.psd", PSD_BYTES, ""),
            ("模型.skp", SKP_BYTES, ""),
            ("备注.txt", "现场量房备注\n".encode("utf-8"), "text/plain"),
        ]
        with _serve(self.ds) as port:
            for name, blob, mime in cases:
                with self.subTest(name=name):
                    url = raw_data_url(blob, mime) if mime else \
                        "data:;base64," + base64.b64encode(blob).decode("ascii")
                    st, d = _post(port, "/api/upload", {"name": name, "data_url": url})
                    self.assertEqual(st, 200, f"{name} 应当收下:{d}")
                    self.assertIn(name, self.intake_names(port), f"{name} 收下了却看不见")

    # ③ 改名伪装:内容签名对不上就拒 —— **每种格式都要问一遍**
    #    四审 subdeepseek:原来只问了 pdf/dwg/xlsx/txt,
    #    剩下 doc/xls/ppt/max/skp/psd/webp/gif/csv/dxf 的签名**删掉仍全绿**。
    def test_d03_disguised_content_rejected(self):
        wrong = b"THIS-IS-NOT-THE-RIGHT-FORMAT-AT-ALL\n" + b"\x00" * 32
        with _serve(self.ds) as port:
            for ext in sorted(ds_web._INBOX_UPLOAD):
                with self.subTest(ext=ext):
                    before = self.inbox_files()
                    st, _ = _post(port, "/api/upload",
                                  {"name": f"假的{ext}", "data_url": raw_data_url(wrong)})
                    self.assertIn(st, (400, None), f"{ext}:内容对不上必须拒")
                    self.assertEqual(self.inbox_files(), before, "拒绝路径必须零写盘")
            # 具体几种最容易被"看起来像"骗过去的,单独再问一次
            for name, blob in [("假的.pdf", png_bytes()),
                               ("假的.dwg", png_bytes()),
                               ("假的.txt", b"\x00\x01\x02\xff\xfe")]:
                with self.subTest(name=name):
                    st, _ = _post(port, "/api/upload",
                                  {"name": name, "data_url": raw_data_url(blob)})
                    self.assertIn(st, (400, None), f"{name} 应当被拒")

    # ④ 超限:**码要说"太大",不能说"内容对不上"**
    #    原来这一幕是**死断言**:夹具造 40MB → 信封超上限 → 服务端在读 body 前就掐断
    #    ⇒ `if d:` 永不成立,那句 assert 一次都没跑过。同一个文件的 u15 注释早就点名
    #    禁止这种写法(四审 subdeepseek 抓到我又犯了一遍)。
    #    改成造一个**刚过单文件上限、但没超信封上限**的文件:能拿到响应,码才问得出来。
    def test_d04_over_per_file_limit_says_too_large(self):
        over = b"%PDF-1.7\n" + b"\x00" * (33 * 1024 * 1024)   # >32MB 但 base64 后 <44MB 信封
        with _serve(self.ds) as port:
            before = self.inbox_files()
            st, d = _post(port, "/api/upload",
                          {"name": "巨图.pdf", "data_url": raw_data_url(over, "application/pdf")})
            self.assertEqual(self.inbox_files(), before, "拒绝路径必须零写盘")
            self.assertIsNotNone(d, "这一档必须能拿到响应体(拿不到 = 这条断言又空跑了)")
            self.assertEqual(st, 400, d)
            self.assertEqual(d.get("error"), "too_large",
                             f"超限要给 too_large,不能给 bad_image(那句话在说'你伪装文件'):{d}")

    def test_d04b_cad_gets_a_bigger_budget(self):
        """>32MB 的 DWG 是这次的**核心场景**(用户原话:特别是 dwg),不能被文档档位挡掉。"""
        big_dwg = b"AC1032" + b"\x00" * (40 * 1024 * 1024)
        with _serve(self.ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "大图纸.dwg", "data_url": raw_data_url(big_dwg)})
            self.assertEqual(st, 200, f"40MB 的 dwg 应当收得下:{d}")
            self.assertIn("大图纸.dwg", self.intake_names(port))

    # ④c UTF-16 的 txt/csv 不许误杀(中文 Windows 记事本存出来就是这个)
    def test_d04c_utf16_text_is_accepted(self):
        blob = "现场量房备注\n客厅 4.2m\n".encode("utf-16")     # 带 BOM
        with _serve(self.ds) as port:
            st, d = _post(port, "/api/upload",
                          {"name": "备注.txt", "data_url": raw_data_url(blob, "text/plain")})
            self.assertEqual(st, 200, f"UTF-16 文本应当收得下:{d}")

    # ⑤ 既有图片行为一条不许退化
    def test_d05_image_rules_do_not_regress(self):
        with _serve(self.ds) as port:
            before = self.inbox_files()
            st, _ = _post(port, "/api/upload", {"name": "x.svg", "data_url": data_url()})
            self.assertIn(st, (400, None), "svg 仍然要拒")
            st, _ = _post(port, "/api/upload",
                          {"name": "a.png", "data_url": data_url(mime="image/gif")})
            self.assertIn(st, (400, None), "图片的 mime 同族闸不许退化")
            self.assertEqual(self.inbox_files(), before, "拒绝路径必须零写盘")
            st, d = _post(port, "/api/upload", {"name": "真图.png", "data_url": data_url()})
            self.assertEqual(st, 200, d)
