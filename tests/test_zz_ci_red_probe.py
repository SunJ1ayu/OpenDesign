"""阶段 A 验收探针:故意失败,确认 CI 红了的 PR 不能合并进 main。

只用于 PR「CI 红必须挡合并(验收探针,不要合并)」;验完关 PR、删分支,永不合并。
"""
import unittest


class CiRedProbe(unittest.TestCase):
    def test_deliberately_red(self):
        self.assertEqual(1, 2, "故意失败:验证红 CI 挡住合并")


if __name__ == "__main__":
    unittest.main()
