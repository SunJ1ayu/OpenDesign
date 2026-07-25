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
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": ctype} if ctype else {}
    data = body if isinstance(body, (bytes, bytearray)) else \
        json.dumps(body, ensure_ascii=False).encode("utf-8")
    conn.request("POST", path, body=data, headers=headers)
    r = conn.getresponse()
    b = r.read()
    conn.close()
    return r.status, (json.loads(b.decode("utf-8")) if b else None)


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
        for n in ["脚本.svg", "程序.exe", "图纸.dwg", "文档.pdf", "存档.zip"]:
            self.rejected(n, "扩展名不在图片白名单(svg 也排除)")

    def test_n12_directory_component_is_stripped_not_trusted(self):
        """即便前端传来带目录的名字,也只取末段(纵深:正则本身也不放行分隔符)。"""
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
        self.assertEqual(st, expect)
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
