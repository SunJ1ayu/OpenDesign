#!/usr/bin/env python3
"""生成更新清单 OpenDesign-update.json(track opendesign-update-check-rate-limit,判据 rl10)。

用法:
    python3 installer/make-update-manifest.py <OpenDesign-Setup-X.exe> win-installer-X [--notes 说明.md] --out OpenDesign-update.json

为什么有它:查更新改成「发布页订阅源 + 每版清单」为主(API 未登录每出口 60 次/小时,业主的 VPN 出口被别人用光)。
清单是新查法里**可信 sha256 的唯一来源** ⇒ 必须**从构建产物本身**算,不许手写或抄。
写完用产品自己的 `ds_update.parse_manifest` 核一遍:产品不认的清单,发出去就是"查得到、装不了"。

发版时和安装包一起传:`gh release create <tag> <exe> OpenDesign-update.json ...`
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_update  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("tag")
    ap.add_argument("--notes")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    name = os.path.basename(args.exe)
    name_m = ds_update.ASSET_RE.match(name)
    tag_m = ds_update.TAG_RE.match(args.tag)
    if not name_m or not tag_m or name_m.group(1) != tag_m.group(1):
        print("✗ 安装包文件名(%s)与标签(%s)的版本对不上 —— 不生成清单" % (name, args.tag), file=sys.stderr)
        return 2

    # 评审(切片 release-ui GLM #2):缺输入要一句人话,不是裸 traceback
    if not os.path.isfile(args.exe):
        print("✗ 找不到安装包:%s —— 不生成清单" % args.exe, file=sys.stderr)
        return 2
    if args.notes and not os.path.isfile(args.notes):
        print("✗ 找不到发布说明文件:%s —— 不生成清单" % args.notes, file=sys.stderr)
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if not os.path.isdir(out_dir):
        print("✗ 清单要写去的目录不存在:%s —— 不生成清单" % out_dir, file=sys.stderr)
        return 2
    h = hashlib.sha256()
    size = 0
    with open(args.exe, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    notes = ""
    if args.notes:
        with open(args.notes, encoding="utf-8") as fh:
            notes = fh.read()

    manifest = {
        "schema": 1,
        "tag": args.tag,
        "version": tag_m.group(1),
        "asset": {"name": name, "size": size, "sha256": h.hexdigest()},
        "notes": notes,
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    try:
        ds_update.parse_manifest(text, args.tag)
    except ValueError as exc:
        print("✗ 产品自己不认这份清单:%s —— 不写出" % exc, file=sys.stderr)
        return 3
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, args.out)
    print("清单已写:%s(%s,%d 字节,sha256 %s…)" % (args.out, name, size, h.hexdigest()[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
