"""判据 rl10:发版时生成更新清单 OpenDesign-update.json(track opendesign-update-check-rate-limit)。

清单是新查法里「可信 sha256」的来源 —— **必须从构建产物本身算**,手写或抄一份等于把整套校验退化成摆设。
生成物必须能被产品自己的核对(ds_update.parse_manifest)原样接受,否则发出去的每一版都"查得到、装不了"。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_update  # noqa: E402

SCRIPT = os.path.join(ROOT, "installer", "make-update-manifest.py")
PY = sys.executable


class MakeUpdateManifest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ds-manifest-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.exe = os.path.join(self.d, "OpenDesign-Setup-0.99.1.exe")
        with open(self.exe, "wb") as fh:
            fh.write(b"MZ" + os.urandom(4096))
        self.notes = os.path.join(self.d, "notes.md")
        with open(self.notes, "w", encoding="utf-8") as fh:
            fh.write("## 这一版改了什么\n\n查更新不怕限流了。\n")
        self.out = os.path.join(self.d, "OpenDesign-update.json")

    def run_script(self, exe, tag):
        return subprocess.run([PY, SCRIPT, exe, tag, "--notes", self.notes, "--out", self.out],
                              capture_output=True, text=True, timeout=60)

    def test_rl10a_digest_and_size_come_from_the_file_itself(self):
        r = self.run_script(self.exe, "win-installer-0.99.1")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            m = json.load(fh)
        with open(self.exe, "rb") as fh:
            data = fh.read()
        self.assertEqual(m["schema"], 1)
        self.assertEqual(m["tag"], "win-installer-0.99.1")
        self.assertEqual(m["version"], "0.99.1")
        self.assertEqual(m["asset"]["name"], "OpenDesign-Setup-0.99.1.exe")
        self.assertEqual(m["asset"]["size"], len(data))
        self.assertEqual(m["asset"]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertIn("查更新不怕限流了", m["notes"])

    def test_rl10b_tag_and_file_name_must_agree(self):
        r = self.run_script(self.exe, "win-installer-0.99.2")
        self.assertNotEqual(r.returncode, 0, "tag 与安装包文件名的版本不一致,却生成了清单")
        self.assertFalse(os.path.exists(self.out), "拒绝了却留下了清单文件")

    def test_rl10d_missing_inputs_say_so_without_a_traceback(self):
        """评审(切片 release-ui GLM #2):安装包 / 说明文件不在时原来是裸 traceback。发版人照着清单做,要一句人话。"""
        cases = {
            "安装包不在": [PY, SCRIPT, os.path.join(self.d, "OpenDesign-Setup-0.99.1.exe.missing"),
                        "win-installer-0.99.1", "--out", self.out],
            "说明文件不在": [PY, SCRIPT, self.exe, "win-installer-0.99.1", "--notes",
                          os.path.join(self.d, "nope.md"), "--out", self.out],
        }
        for why, argv in cases.items():
            with self.subTest(why):
                if why == "安装包不在":
                    argv[2] = os.path.join(self.d, "missing", "OpenDesign-Setup-0.99.1.exe")
                r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn("Traceback", r.stderr, r.stderr)
                self.assertIn("✗", r.stderr)
                self.assertFalse(os.path.exists(self.out))

    def test_rl10c_the_product_accepts_what_the_script_writes(self):
        r = self.run_script(self.exe, "win-installer-0.99.1")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            text = fh.read()
        asset = ds_update.parse_manifest(text, "win-installer-0.99.1", ds_update.REPO)
        with open(self.exe, "rb") as fh:
            self.assertEqual(asset["digest"], "sha256:" + hashlib.sha256(fh.read()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
