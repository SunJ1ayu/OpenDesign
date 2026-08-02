"""O2 无环闸:`bin/ds_*.py` 之间的 import 不许成环(含函数内延迟 import)。

track opendesign-structure-debt。**主 agent 亲写,执行腿逐字节 off-limits。**

为什么不是"能跑就行":这些环**现在就能跑** —— 靠的正是"把 import 藏进函数里"
(`ds_workspace.py` 里还专门写了段注释辩解)。延迟 import 让环在运行期不炸,
于是环可以一直活着没人管。**这条判据查的是静态结构,不是运行期行为。**

首跑战果(2026-08-02):主 agent 人肉审出 2 个环,**检测器找出 4 个** ——
多出来的 `ds_tools ⇄ ds_lint` 我通篇没看见。教训:结构判断靠人眼不完备,
这正是"机械闸"该存在的理由。第 4 个环不在本单 Scope(见 tasks.md 的 Scope 说明)。

同时钉住:那段辩解注释必须删掉。留着 = 注释撒谎,而"注释撒谎"是这个仓库
已经记在账上的另一条债(`ds_web.py:597` 说"取项目头"实为全文搜索)。
"""
import ast
import os
import unittest

import structure_moves as sm

LOCAL_PREFIX = "ds_"


def _all_deps(path: str) -> set[str]:
    """收**全部** import —— 模块层的和函数体里延迟的,一视同仁。

    ⚠️ 这里踩过一次坑,记下来:我最初只收模块层 import,理由是"延迟 import 是绕开
    环的手段,不该算边"。**红检当场证伪**:两处环恰恰全靠延迟 import 成的,
    只收模块层的话现在就没有环 —— 那条判据无论做不做事都绿,是假绿。

    正确的读法:延迟 import **就是**依赖,只是把爆炸时间从加载期推到调用期。
    藏起来的环仍然是环。要判"环真的解开了",必须把藏起来的那条边也算上。
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    deps: set[str] = set()
    for node in ast.walk(tree):                  # 全树,不只顶层
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith(LOCAL_PREFIX):
                    deps.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(LOCAL_PREFIX):
                deps.add(node.module)
    return deps


def _build_graph() -> dict[str, set[str]]:
    graph = {}
    for fn in sorted(os.listdir(sm.BIN)):
        if not (fn.startswith(LOCAL_PREFIX) and fn.endswith(".py")):
            continue
        graph[fn[:-3]] = _all_deps(os.path.join(sm.BIN, fn))
    return graph


def _canon(cycle: list[str]) -> tuple[str, ...]:
    """把一条环路径归一化成**与起点无关**的表示。

    ⚠️ 2026-08-02 踩到:DFS 报出来的环是「一条路径」,起点取决于遍历顺序。
    删掉一个**不相干**的死 import 后,`ds_intake→ds_organize→ds_intake` 变成了
    `ds_organize→ds_intake→ds_organize` —— 同一个环、不同写法,白名单按字面比对
    就把它误判成"新引入的环"。
    归一化 = 去掉重复的末节点,再旋转到字典序最小的节点开头。
    (subkimi 在 panel-review 里点了这个方向:DFS 的环枚举依赖遍历顺序。)
    """
    nodes = cycle[:-1] if len(cycle) > 1 and cycle[0] == cycle[-1] else cycle[:]
    if not nodes:
        return ()
    i = nodes.index(min(nodes))
    return tuple(nodes[i:] + nodes[:i])


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """返回所有环(每个环一条路径),DFS + 栈回溯。"""
    cycles, stack, on_stack, seen = [], [], set(), set()

    def walk(node: str):
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(graph.get(node, ())):
            if nxt not in graph:                 # 不在 bin/ 的外部模块,跳过
                continue
            if nxt in on_stack:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif nxt not in seen:
                walk(nxt)
        stack.pop()
        on_stack.discard(node)
        seen.add(node)

    for n in sorted(graph):
        if n not in seen:
            walk(n)
    return cycles


# ── 已知残留环:**全部出自"工具登记处"层**,不在本单 Scope ────────────────────
# ds_organize / ds_tools / ds_refs 三个业务模块兼职注册 29 个 MCP 工具,
# 登记处需要反向 import 别的业务模块 → 成环。这是第 ③ 刀要解决的,单独起 track。
# 本单只杀 taxonomy 那一个(它的成因不同:公共配置表寄居在 ds_intake)。
#
# ⚠️ 这份白名单**只许缩短,不许加长**。加一行 = 新引入了一个环,那是 BLOCK。
# 均为 `_canon` 归一化形式(与起点无关),三条的**反向边**都在登记处:
# 🔴 2026-08-02 track opendesign-mcp-registry(方向 R)**清空这份清单**。
# 用户在三条路里选了 R(一次做对):登记层移出业务模块 + 统一入口 bin/ds_mcp.py,
# config 改一次。⇒ 三条反向边全部消失,**残留应为空集**。
# 选 D(只搬登记层、保留旧入口)会留下 3 个「入口 ⇄ 自己的 server」自环 ——
# 我实测验证过(subdeepseek 说"归零"是错的);R 没有这个尾巴,因为入口不再是业务模块。
KNOWN_REMAINING: set[tuple[str, ...]] = set()
# 第①刀杀掉的那个(taxonomy 错位),留作回归护栏 —— 它不许复活:
TARGET_CYCLE = ("ds_intake", "ds_workspace")


class NoImportCycles(unittest.TestCase):

    def test_01_本单目标环已消失(self):
        """taxonomy 那个环必须死 —— 这是本单第 ① 刀的通过条件。"""
        cycles = {_canon(c) for c in _find_cycles(_build_graph())}
        self.assertNotIn(
            TARGET_CYCLE, cycles,
            "`ds_intake ⇄ ds_workspace` 仍成环 —— taxonomy 还没搬出去")

    def test_02_没有引入新环(self):
        """残留环只许是已知的那三个;多一个 = 本单把事情弄坏了。

        注意这条**不是**"无环"。本单只杀一个环,拿"全无环"当通过条件是自欺:
        它永远红,红了也说明不了本单做没做对。
        """
        cycles = {_canon(c) for c in _find_cycles(_build_graph())}
        unexpected = cycles - KNOWN_REMAINING - {TARGET_CYCLE}
        pretty = ["  " + " → ".join(c) for c in sorted(unexpected)]
        self.assertEqual(unexpected, set(),
                         "引入了新的循环依赖:\n" + "\n".join(pretty))

    def test_02b_白名单必须是空的(self):
        """护栏:方向 R 做完后这份清单就该是空集,**再往里加一行都是 BLOCK**。

        (第①②刀时它是"≤3";R 的全部卖点就是把那 3 条清零 ——
        如果实现改不动它,那说明选 R 没拿到该拿的东西,应该退回去重选方向。)
        """
        self.assertEqual(
            KNOWN_REMAINING, set(),
            "KNOWN_REMAINING 非空 —— 方向 R 的通过条件就是它为空;"
            "加白名单不是修环的办法")

    def test_02c_ds_workspace_不再有延迟import的辩解注释(self):
        """环解开之后,这段注释就必须消失 —— 它描述的机制已经不存在了。"""
        with open(sm.module_path("ds_workspace"), encoding="utf-8") as fh:
            text = fh.read()
        stale = [p for p in ("函数内延迟 import", "模块层反向 import 会成环")
                 if p in text]
        self.assertEqual(
            stale, [],
            f"`ds_workspace.py` 里仍有 {stale} —— 环已解开,"
            "这段辩解注释必须删掉,留着就是注释撒谎")

    def test_03_环检测器本身是灵的(self):
        """护栏题:喂一个人造的环进去,检测器必须抓到。

        没有这条,`test_01` 变绿也可能是因为检测器坏了(比如 graph 建空了)。
        """
        fake = {"ds_a": {"ds_b"}, "ds_b": {"ds_c"}, "ds_c": {"ds_a"}}
        self.assertNotEqual(_find_cycles(fake), [], "检测器抓不到人造环")
        self.assertEqual(_find_cycles({"ds_a": {"ds_b"}, "ds_b": set()}), [],
                         "检测器把无环图误报成有环")


if __name__ == "__main__":
    unittest.main()
