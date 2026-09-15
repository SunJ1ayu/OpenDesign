#!/usr/bin/env python3
"""Windows 更新端到端(e1~e5)用的 **GitHub 替身** + 目录清单工具。

track opendesign-in-app-update-install §3。**只在用完就扔的 CI runner 上跑。**

软件查更新问的是逐字节钉死的 `https://api.github.com/repos/<repo>/releases`(t11),
下载照抄 GitHub 给的 `browser_download_url`(t14)。CI 上要让它看见一个新版,
又**不能在真仓库发测试 release**(业主的软件也会看见)、**不能给产品开改向口**
⇒ runner 上用 hosts 把两个域名指到本机,由这里冒充,证书的 CA 导进那台机器的受信根。
产品代码零改动。

子命令:

    releases  --repo R --version V --setup EXE           打印替身会给出的 releases JSON
    serve     --repo R --version V --setup EXE --cert C --key K --mode-file F --log L [--port 443]
    manifest  DIR OUT                                    写目录清单,stdout 打印 "<digest> <文件数>"
    diff      A B                                        两份清单的差异(最多 30 行)

`--mode-file` 里写 `normal` 或 `corrupt`(翻一个字节),每个请求现读,脚本不用重启。
`--source-file` 里写 `feed`(默认)或 `api`,同样现读(track opendesign-update-check-rate-limit,判据 rl12):
  feed —— `github.com/<repo>/releases.atom` 与每版清单 `OpenDesign-update.json` 照真 GitHub 的样子给,
          **api.github.com 回 403 `rate limit exceeded`**(业主 09-15 夜实测的原话);
  api  —— 订阅源回 503,API 照常 —— 问的是"订阅源坏了还能不能靠 API 更新"。
  清单请求带 `Accept: application/json` 一律 404:真 GitHub 的下载地址就是这样(rl8e)。
`--log` 每个请求追加一行 JSON(判定器拿它确认"软件真的来问过、真的下过")。

🔴 releases JSON 的形状由 `tests/test_update_e2e_harness.py` 直接喂给真的
   `ds_update.decide()` 验过 —— 替身给的东西产品不认,CI 那一趟就白跑了。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

TAG_FMT = "win-installer-{version}"
ASSET_FMT = "OpenDesign-Setup-{version}.exe"

# 活树比对排除的目录名:python 运行时往 ds\bin 写字节码缓存,那不是安装器管的文件。
# **只排这一个**,而且按目录名精确匹配 —— 别的差异一律进清单、让场景红。
MANIFEST_SKIP_DIRS = frozenset({"__pycache__"})


def sha256_file(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def releases_json(repo, version, setup_path):
    tag = TAG_FMT.format(version=version)
    name = ASSET_FMT.format(version=version)
    return [{
        "tag_name": tag,
        "name": "OpenDesign %s (e2e)" % version,
        "draft": False,
        "prerelease": True,
        "html_url": "https://github.com/%s/releases/tag/%s" % (repo, tag),
        "body": "e2e stand-in release",
        "assets": [{
            "name": name,
            "browser_download_url": "https://github.com/%s/releases/download/%s/%s" % (repo, tag, name),
            "size": os.path.getsize(setup_path),
            "digest": "sha256:" + sha256_file(setup_path),
        }],
    }]


def atom_path(repo):
    return "/%s/releases.atom" % repo


def atom_xml(repo, version):
    """与真 releases.atom 同形(命名空间、entry、`<link href=".../releases/tag/<tag>">`),只有一个 entry。"""
    tag = TAG_FMT.format(version=version)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xml:lang="en-US">\n'
        '  <id>tag:github.com,2008:https://github.com/%(repo)s/releases</id>\n'
        '  <title>Release notes from OpenDesign</title>\n'
        '  <entry>\n'
        '    <id>tag:github.com,2008:Repository/1/%(tag)s</id>\n'
        '    <link rel="alternate" type="text/html" href="https://github.com/%(repo)s/releases/tag/%(tag)s"/>\n'
        '    <title>OpenDesign %(version)s (e2e stand-in)</title>\n'
        '    <content type="html">&lt;p&gt;e2e&lt;/p&gt;</content>\n'
        '  </entry>\n'
        '</feed>\n' % {"repo": repo, "tag": tag, "version": version})


def update_manifest_path(repo, version):
    return "/%s/releases/download/%s/OpenDesign-update.json" % (repo, TAG_FMT.format(version=version))


def update_manifest(version, setup_path):
    """与 installer/make-update-manifest.py 写出的同形(schema 1)。"""
    return {
        "schema": 1,
        "tag": TAG_FMT.format(version=version),
        "version": version,
        "asset": {"name": ASSET_FMT.format(version=version), "size": os.path.getsize(setup_path),
                  "sha256": sha256_file(setup_path)},
        "notes": "e2e stand-in",
    }


def download_path(repo, version):
    return "/%s/releases/download/%s/%s" % (
        repo, TAG_FMT.format(version=version), ASSET_FMT.format(version=version))


def corrupt(data: bytes) -> bytes:
    """翻中间一个字节。大小不变 ⇒ 只有 sha256 分得出来(这正是 e2 要问的)。"""
    mid = len(data) // 2
    return data[:mid] + bytes([data[mid] ^ 0xFF]) + data[mid + 1:]


def make_handler(repo, version, setup_path, mode_file, log_path, source_file=None):
    api_path = "/repos/%s/releases" % repo
    dl_path = download_path(repo, version)
    feed_path = atom_path(repo)
    manifest_path = update_manifest_path(repo, version)
    body_json = json.dumps(releases_json(repo, version, setup_path)).encode("utf-8")
    body_atom = atom_xml(repo, version).encode("utf-8")
    body_manifest = json.dumps(update_manifest(version, setup_path)).encode("utf-8")
    rate_limited = json.dumps({"message": "API rate limit exceeded for 127.0.0.1. (But here's the good news: "
                               "Authenticated requests get a higher rate limit.)"}).encode("utf-8")

    def source():
        try:
            with open(source_file, encoding="utf-8") as fh:
                return fh.read().strip() or "feed"
        except (OSError, TypeError):
            return "feed"

    def mode():
        try:
            with open(mode_file, encoding="utf-8") as fh:
                return fh.read().strip() or "normal"
        except OSError:
            return "normal"

    def log(entry):
        entry["t"] = time.time()
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 不往 stderr 刷,事实进 --log
            pass

        def _send(self, code, ctype, payload, reason=None):
            self.send_response(code, reason)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlsplit(self.path).path
            host = self.headers.get("Host", "")
            src = source()
            if path == api_path:
                if src == "feed":
                    log({"kind": "releases", "host": host, "path": self.path, "status": 403, "source": src})
                    self._send(403, "application/json", rate_limited, "rate limit exceeded")
                else:
                    log({"kind": "releases", "host": host, "path": self.path, "status": 200, "source": src})
                    self._send(200, "application/json", body_json)
            elif path == feed_path:
                if src == "feed":
                    log({"kind": "atom", "host": host, "status": 200, "source": src})
                    self._send(200, "application/atom+xml; charset=utf-8", body_atom)
                else:
                    log({"kind": "atom", "host": host, "status": 503, "source": src})
                    self._send(503, "text/plain", b"feed unavailable (e2e api mode)")
            elif path == manifest_path:
                if "json" in (self.headers.get("Accept") or "").lower():
                    log({"kind": "manifest", "host": host, "status": 404, "accept": self.headers.get("Accept")})
                    self._send(404, "text/plain", b"Not Found")
                else:
                    log({"kind": "manifest", "host": host, "status": 200, "accept": self.headers.get("Accept")})
                    self._send(200, "application/octet-stream", body_manifest)
            elif path == dl_path:
                m = mode()
                with open(setup_path, "rb") as fh:
                    data = fh.read()
                if m == "corrupt":
                    data = corrupt(data)
                log({"kind": "download", "host": host, "mode": m, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()})
                self._send(200, "application/octet-stream", data)
            else:
                log({"kind": "unknown", "host": host, "path": self.path})
                self._send(404, "text/plain", b"not found")

    return Handler


def serve(args):
    handler = make_handler(args.repo, args.version, args.setup, args.mode_file, args.log,
                           source_file=args.source_file)
    httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(args.cert, args.key)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print("fake-github listening on %s:%d" % (args.bind, args.port), flush=True)
    httpd.serve_forever()


def manifest(root):
    """{相对路径(正斜杠): sha256}。跳过 MANIFEST_SKIP_DIRS。"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in MANIFEST_SKIP_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[rel] = sha256_file(full)
    return out


def manifest_digest(entries):
    canon = json.dumps(entries, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def diff_lines(a, b, limit=30):
    lines = []
    for rel in sorted(set(a) | set(b)):
        if rel not in b:
            lines.append("- " + rel)
        elif rel not in a:
            lines.append("+ " + rel)
        elif a[rel] != b[rel]:
            lines.append("~ " + rel)
    more = len(lines) - limit
    return lines[:limit] + (["... %d more" % more] if more > 0 else [])


def main(argv):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("releases", "serve"):
        s = sub.add_parser(name)
        s.add_argument("--repo", required=True)
        s.add_argument("--version", required=True)
        s.add_argument("--setup", required=True)
        if name == "serve":
            s.add_argument("--cert", required=True)
            s.add_argument("--key", required=True)
            s.add_argument("--mode-file", required=True)
            s.add_argument("--log", required=True)
            s.add_argument("--source-file")
            s.add_argument("--bind", default="127.0.0.1")
            s.add_argument("--port", type=int, default=443)
    m = sub.add_parser("manifest")
    m.add_argument("dir")
    m.add_argument("out")
    d = sub.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")
    args = p.parse_args(argv)

    if args.cmd == "releases":
        print(json.dumps(releases_json(args.repo, args.version, args.setup), indent=2))
    elif args.cmd == "serve":
        serve(args)
    elif args.cmd == "manifest":
        if not os.path.isdir(args.dir):
            print("MISSING 0")
            return 0
        entries = manifest(args.dir)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, sort_keys=True, ensure_ascii=True)
        print("%s %d" % (manifest_digest(entries), len(entries)))
    elif args.cmd == "diff":
        with open(args.a, encoding="utf-8") as fa, open(args.b, encoding="utf-8") as fb:
            for line in diff_lines(json.load(fa), json.load(fb)):
                print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
