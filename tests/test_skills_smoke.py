#!/usr/bin/env python3
"""SkillsLoader 机械化冒烟 — track opendesign-windows-prep T6。

frontmatter 写坏时 skill 会静默不进系统提示词(人工走查看不出),这里用 nanobot
真实的 SkillsLoader 解析 repo 内 skills/,断言 organize/refs 真的会被加载。

跑法:  /root/.venvs/design-studio/bin/python tests/test_skills_smoke.py
(系统 python 无 nanobot 时整套 skip,不算失败——与 MCP 表面测试同款惯例)
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/(其下 skills/ 即 workspace 布局)

try:
    from pathlib import Path
    from nanobot.agent.skills import SkillsLoader
    HAS_NANOBOT = True
except ImportError:
    HAS_NANOBOT = False


@unittest.skipUnless(HAS_NANOBOT, "nanobot 未装(用 /root/.venvs/design-studio/bin/python 跑)")
class TestSkillsSmoke(unittest.TestCase):

    def setUp(self):
        self.loader = SkillsLoader(Path(ROOT))

    # ① 两个 skill 都被发现且可用
    def test_01_discovered(self):
        names = {s["name"] for s in self.loader.list_skills()}
        self.assertIn("organize", names)
        self.assertIn("refs", names)

    # ② frontmatter description 被正确解析(坏 frontmatter 会 fallback 成目录名)
    def test_02_descriptions_parsed(self):
        summary = self.loader.build_skills_summary()
        self.assertIn("**organize** — 整理电脑文件夹", summary)
        self.assertIn("**refs** — 参考图管理", summary)

    # ③ 全文可加载且 frontmatter 被剥离(进上下文的是正文)
    def test_03_loadable_for_context(self):
        content = self.loader.load_skills_for_context(["organize", "refs"])
        self.assertIn("四步,一步不许跳", content)
        self.assertIn("永远不动图片文件本身", content)
        self.assertNotIn("---\nname:", content)

    # ④ 可达性不变量:本项目禁了内置文件工具(tools.file.enable=false,防脑裂),
    #    nanobot 按需加载路径(summary 让模型 read_file 拉全文)因此是死路——
    #    随附 skill 必须全部 always: true 直接进系统提示词,否则模型永远够不到。
    #    扫全部 workspace skill 而非点名:新增 skill 忘标 always 会在这里变红。
    def test_04_workspace_skills_all_always(self):
        ours = {s["name"] for s in self.loader.list_skills(filter_unavailable=False)
                if s["source"] == "workspace"}
        always = set(self.loader.get_always_skills())
        self.assertTrue(ours, "workspace skills 一个都没发现,布局坏了")
        self.assertEqual(ours - always, set(),
                         "这些 skill 没标 always: true,文件工具已禁,模型够不到它们")


if __name__ == "__main__":
    unittest.main(verbosity=2)
