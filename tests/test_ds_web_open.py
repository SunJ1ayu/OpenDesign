#!/usr/bin/env python3
"""ds_web「打开文件」受控开口 oracle — track opendesign-frontend-p3-polish §I4。

跑法:  python3 tests/test_ds_web_open.py

背景:`POST /api/open-folder` 原本只放行**目录**(resolve_sub 带 isdir 闸),是
"只读铁律的唯一受控例外"。修改单 §I4 要求「最近更新」文件行点击用系统默认程序打开
该文件 —— 这把开口从目录拓宽到文件,等于把 os.startfile / xdg-open 喂给任意扩展名。
本 oracle 就是这道拓宽的安全闸判据。

契约(design.md §I4):body 新增可选 `rel`(相对项目夹的文件路径),闸序对齐既有
`_files_file` 先例:
  Gate A  ds_workspace.relpath_ok(rel)         禁 \\ % 控制符与 . / .. 段
  Gate B  realpath + ds_common.within(项目夹)   逃逸权威闸
  Gate D  os.path.isfile(target)                目录/不存在一律 404(开目录走 sub)
  Gate C  扩展名 ∈ ds_web._OPEN_EXTS 白名单      拒一切可执行/脚本/快捷方式
(D 先于 C 是有意的:只有确定是真文件才谈得上"扩展名被拒"415,否则目录会拿到
 415 这种自相矛盾的码。安全性不受顺序影响——两闸都必须过才调 launcher。)
全过才调 OPEN_LAUNCHER;**任何拒绝路径 launcher 调用数必须为 0**(本文件的核心断言)。
rel 与 sub 互斥,同给 → 400(不猜意图)。

red-check(commit message 附结果):
  未实现 rel 时,服务把 rel 当未知字段忽略 → 退化为"打开项目夹",
  test_open_file_allowlisted 断言 launcher 收到文件路径 → 红;
  test_open_file_executable_rejected 断言 415 → 实得 200 → 红。
  实现后再逐条拆闸复验:去 Gate C → executable 组变红;去 Gate B → symlink/traversal 变红。
纯 stdlib、离线、端口 0;启动器一律注入 fake,测试永不真开文件。
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
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_web  # noqa: E402

KEY = "龙腾世纪-1802"
PROJ_REL = "01-项目/20260612 周宁 龙腾世纪 12#1802"
PNG = b"\x89PNG\r\n\x1a\n"

# 白名单内(设计师会双击的图纸/文档/图片)
OK_FILES = [
    "03-CAD/平面.dwg",
    "03-CAD/轴网.dxf",
    "04-模型/主卧.skp",
    "05-文档/报价.xlsx",
    "05-文档/合同.docx",
    "05-文档/说明.pdf",
    "05-文档/备忘.txt",
    "06-效果图/客厅.png",
    "06-效果图/餐厅.jpg",
]
# 白名单外:可执行 / 脚本 / 快捷方式 / 无扩展名 —— 一个都不许开
BAD_EXT_FILES = [
    "03-CAD/装机.exe",
    "03-CAD/跑批.bat",
    "03-CAD/脚本.ps1",
    "03-CAD/快捷方式.lnk",
    "03-CAD/宏.vbs",
    "03-CAD/挂载.sh",
    "03-CAD/无扩展名",
    "03-CAD/报价.pdf.bat",   # 双扩展名:真实扩展是 .bat
    "03-CAD/矢量.svg",       # 既有图片白名单也排除 svg(可执行脚本载体)
]


def _touch(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _mkroot() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_open_")
    ws = os.path.join(d, "ws")
    proj = os.path.join(ws, *PROJ_REL.split("/"))
    for rel in OK_FILES + BAD_EXT_FILES:
        _touch(os.path.join(proj, *rel.split("/")), PNG)
    _touch(os.path.join(proj, "05-文档", "大写.PDF"), PNG)   # 大小写归一
    os.makedirs(os.path.join(proj, "07-空目录"), exist_ok=True)
    # 工作区外的敏感目标 + 指向它的符号链接(Gate B 逃逸测试)
    _touch(os.path.join(d, "secret", "密钥.txt"), b"LEAK")
    _touch(os.path.join(d, "secret", "木马.exe"), b"LEAK")
    os.symlink(os.path.join(d, "secret"), os.path.join(proj, "03-CAD", "外链"))
    os.makedirs(os.path.join(d, "config"), exist_ok=True)
    with open(os.path.join(d, "config", "workspace.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"root": ws, "projects": {KEY: PROJ_REL}}, fh,
                  ensure_ascii=False)
    return d


def _mkdist() -> str:
    d = tempfile.mkdtemp(prefix="ds_web_open_dist_")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><div>x</div>")
    return d


@contextmanager
def _serve(root: str):
    calls = []
    httpd = ds_web.make_server(root, _mkdist(), port=0)
    old = ds_web.OPEN_LAUNCHER
    ds_web.OPEN_LAUNCHER = calls.append
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1], calls
    finally:
        ds_web.OPEN_LAUNCHER = old
        httpd.shutdown()
        httpd.server_close()


def _post(port, body, path="/api/open-folder"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    payload = (json.dumps(body).encode("utf-8") if isinstance(body, dict)
               else body)
    conn.request("POST", path, body=payload,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data.decode("utf-8")) if data else None)


def _projdir(root: str) -> str:
    return os.path.realpath(os.path.join(root, "ws", *PROJ_REL.split("/")))


class OpenFileAllowlist(unittest.TestCase):
    """Gate C 正向:白名单内文件真的开,且开的是它自己(不是项目夹)。"""

    def test_open_file_allowlisted(self):
        root = _mkroot()
        with _serve(root) as (port, calls):
            for rel in OK_FILES:
                calls.clear()
                st, _ = _post(port, {"key": KEY, "rel": rel})
                self.assertEqual(st, 200, f"{rel} 应放行")
                self.assertEqual(len(calls), 1, f"{rel} 应恰好启动一次")
                self.assertEqual(
                    calls[0],
                    os.path.join(_projdir(root), *rel.split("/")),
                    f"{rel} 启动目标必须是该文件本身",
                )

    def test_open_file_ext_case_insensitive(self):
        """扩展名大小写归一:.PDF 与 .pdf 同权。"""
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _ = _post(port, {"key": KEY, "rel": "05-文档/大写.PDF"})
            self.assertEqual(st, 200)
            self.assertEqual(len(calls), 1)


class OpenFileRejects(unittest.TestCase):
    """一切拒绝路径:状态码对 + **launcher 零调用**(本 oracle 的核心不变量)。"""

    def _reject(self, body, want_status, msg):
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _ = _post(port, body)
            self.assertEqual(st, want_status, msg)
            self.assertEqual(calls, [], f"{msg}:拒绝路径必须零执行,实得 {calls}")

    def test_executable_and_script_rejected(self):
        """Gate C 反向:可执行/脚本/快捷方式/无扩展名/双扩展名 一律 415 零执行。"""
        for rel in BAD_EXT_FILES:
            self._reject({"key": KEY, "rel": rel}, 415, f"{rel} 必须被白名单拒绝")

    def test_traversal_rejected(self):
        """Gate A:.. 段 / 反斜杠 / % / 控制符 一律 404 零执行。"""
        for rel in [
            "../../../etc/passwd",
            "03-CAD/../../../secret/密钥.txt",
            "..",
            ".",
            "./03-CAD/平面.dwg",
            "03-CAD\\平面.dwg",
            "03-CAD/%2e%2e/平面.dwg",
            "03-CAD/\u0001平面.dwg",  # 裸控制符改显式转义(源码可见)
            "03-CAD//平面.dwg",
        ]:
            self._reject({"key": KEY, "rel": rel}, 404, f"{rel!r} 必须被路径闸拒绝")

    def test_symlink_escape_rejected(self):
        """Gate B:项目夹内的符号链接指向夹外 → 404 零执行(即便扩展名白名单内)。"""
        self._reject({"key": KEY, "rel": "03-CAD/外链/密钥.txt"}, 404,
                     "符号链接逃逸必须被 within 闸拒绝")

    def test_symlink_escape_to_executable_rejected(self):
        self._reject({"key": KEY, "rel": "03-CAD/外链/木马.exe"}, 404,
                     "逃逸到夹外可执行文件必须被拒")

    def test_directory_rejected(self):
        """Gate D:rel 指向目录 → 404(开目录走 sub,不走 rel)。"""
        self._reject({"key": KEY, "rel": "07-空目录"}, 404, "rel 指目录必须拒")
        self._reject({"key": KEY, "rel": "03-CAD"}, 404, "rel 指目录必须拒")

    def test_missing_file_rejected(self):
        self._reject({"key": KEY, "rel": "03-CAD/不存在.dwg"}, 404, "不存在的文件必须拒")

    def test_rel_and_sub_mutually_exclusive(self):
        """rel 与 sub 同给 → 400,不猜意图。"""
        self._reject({"key": KEY, "rel": "03-CAD/平面.dwg", "sub": "03-CAD"},
                     400, "rel+sub 同给必须 400")

    def test_rel_bad_type_rejected(self):
        for bad in [123, True, [], {}, "", None]:
            # None 走 JSON null:与"未给 rel"区分不开会退化成开项目夹 —— 显式拒
            self._reject({"key": KEY, "rel": bad}, 400,
                         f"rel={bad!r} 类型非法必须 400")

    def test_unknown_key_rejected(self):
        self._reject({"key": "不存在的项目", "rel": "03-CAD/平面.dwg"}, 404,
                     "未知 key 必须 404")


class OpenFolderNotRegressed(unittest.TestCase):
    """老 sub 行为(目录)一字不变 —— 拓宽不许回归。"""

    def test_open_project_root_still_works(self):
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _ = _post(port, {"key": KEY})
            self.assertEqual(st, 200)
            self.assertEqual(calls, [_projdir(root)])

    def test_open_subdir_still_works(self):
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _ = _post(port, {"key": KEY, "sub": "03-CAD"})
            self.assertEqual(st, 200)
            self.assertEqual(calls, [os.path.join(_projdir(root), "03-CAD")])

    def test_sub_pointing_at_file_still_rejected(self):
        """老闸:sub 必须是目录,指向文件仍 404 零执行。"""
        root = _mkroot()
        with _serve(root) as (port, calls):
            st, _ = _post(port, {"key": KEY, "sub": "平面.dwg"})
            self.assertEqual(st, 404)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
