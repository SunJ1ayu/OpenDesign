#!/usr/bin/env python3
"""ds_intake 收件箱认领核心的 oracle — track opendesign-intake design.md。

跑法:  python3 tests/test_ds_intake.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心。

铁律(与 design 对账):
- 规则表 = config/taxonomy.default.json(仓内)+ <ds_root>/config/taxonomy.json
  覆盖;坏用户配置 = 功能整体降级(None),不静默猜。
- 建议是确定性的:扩展名→类目;项目 token 唯一命中才建议,歧义留空。
- stage_intake 只构造 operations 并直调 ds_organize.stage_plan —— 校验/冲突/
  快照/approve 硬闸全复用,本模块自己不发明执行路径。
"""
import json
import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_intake    # noqa: E402
import ds_organize  # noqa: E402


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


PROJ_A = "20260612 周宁 龙腾世纪 12#1802"
PROJ_B = "20260701 陈晨 万科城 3#601"


class IntakeBase(unittest.TestCase):
    """夹具:临时 ds_root(workspace.json/taxonomy 覆盖落这)+ 临时工作区
    (00-收件箱 / 01-项目/两个项目夹 / 03-共享资源)。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsintake-ds-")
        self.ws = tempfile.mkdtemp(prefix="dsintake-ws-")
        self.inbox = os.path.join(self.ws, "00-收件箱")
        os.makedirs(self.inbox)
        for proj in (PROJ_A, PROJ_B):
            os.makedirs(os.path.join(self.ws, "01-项目", proj))
        os.makedirs(os.path.join(self.ws, "03-共享资源", "参考图库"))
        _write(os.path.join(self.ds, "config", "workspace.json"),
               json.dumps({"root": self.ws, "projects": {}}, ensure_ascii=False))
        self.allowed = [self.ws]

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)
        shutil.rmtree(self.ws, ignore_errors=True)


class TaxonomyOracle(IntakeBase):
    def test_01_default_taxonomy_loads(self):
        tax = ds_intake.load_taxonomy(self.ds)
        self.assertIsNotNone(tax)
        ids = {c["id"] for c in tax["categories"]}
        self.assertIn("参考图", ids)
        self.assertIn("CAD", ids)

    def test_02_suggest_by_extension(self):
        tax = ds_intake.load_taxonomy(self.ds)
        cat = ds_intake.suggest_category("玄关参考.JPG", tax)  # 大小写不敏感
        self.assertEqual(cat["id"], "参考图")
        self.assertEqual(cat["scope"], "workspace")
        cat = ds_intake.suggest_category("平面图.dwg", tax)
        self.assertEqual(cat["id"], "CAD")
        self.assertEqual(cat["mode"], "suggest")  # 被引用类目
        self.assertIsNone(ds_intake.suggest_category("奇怪文件.xyz", tax))
        self.assertIsNone(ds_intake.suggest_category("无扩展名", tax))

    def test_03_user_overlay_replaces_toplevel_key(self):
        _write(os.path.join(self.ds, "config", "taxonomy.json"),
               json.dumps({"categories": [
                   {"id": "只有一类", "scope": "project", "dir": "99-其他",
                    "extensions": [".xyz"], "mode": "auto"}]}, ensure_ascii=False))
        tax = ds_intake.load_taxonomy(self.ds)
        self.assertEqual([c["id"] for c in tax["categories"]], ["只有一类"])
        # 未覆盖的顶层键保默认
        self.assertIn("00-收件箱", tax["inboxDirs"])
        self.assertEqual(ds_intake.suggest_category("a.xyz", tax)["id"], "只有一类")

    def test_04_bad_user_overlay_degrades_whole(self):
        _write(os.path.join(self.ds, "config", "taxonomy.json"), "{broken json")
        self.assertIsNone(ds_intake.load_taxonomy(self.ds))
        # 结构不对同样降级(categories 不是 list)
        _write(os.path.join(self.ds, "config", "taxonomy.json"),
               json.dumps({"categories": "nope"}))
        self.assertIsNone(ds_intake.load_taxonomy(self.ds))


class ListInboxOracle(IntakeBase):
    def test_05_lists_files_with_suggestions(self):
        _write(os.path.join(self.inbox, "龙腾世纪玄关参考.jpg"))
        _write(os.path.join(self.inbox, "户型图.dwg"))
        _write(os.path.join(self.inbox, "神秘文件.xyz"))
        r = ds_intake.list_inbox(self.ds)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["inbox"], "00-收件箱")
        by = {e["name"]: e for e in r["entries"]}
        self.assertEqual(by["龙腾世纪玄关参考.jpg"]["category"]["id"], "参考图")
        # 项目 token 唯一命中(龙腾世纪只在 PROJ_A)
        self.assertEqual(by["龙腾世纪玄关参考.jpg"]["project"], PROJ_A)
        self.assertEqual(by["户型图.dwg"]["category"]["id"], "CAD")
        self.assertIsNone(by["户型图.dwg"]["project"])  # 无 token 命中=留空
        self.assertIsNone(by["神秘文件.xyz"]["category"])

    def test_06_project_token_ambiguity_stays_empty(self):
        # "周宁" 只在 A;造一个同地点项目让它歧义
        os.makedirs(os.path.join(self.ws, "01-项目", "20260801 周宁 龙腾世纪 5#301"))
        _write(os.path.join(self.inbox, "龙腾世纪客厅.jpg"))
        r = ds_intake.list_inbox(self.ds)
        e = r["entries"][0]
        self.assertIsNone(e["project"])  # 两个项目都含"龙腾世纪"→歧义不猜

    def test_07_dirs_listed_without_category(self):
        os.makedirs(os.path.join(self.inbox, "业主发来的一批图"))
        _write(os.path.join(self.inbox, "业主发来的一批图", "1.jpg"))
        r = ds_intake.list_inbox(self.ds)
        e = [x for x in r["entries"] if x["name"] == "业主发来的一批图"][0]
        self.assertEqual(e["type"], "dir")
        self.assertIsNone(e["category"])  # 整夹不拆散,不给扩展名建议

    def test_08_inbox_candidates_and_missing(self):
        # 候选名容错:换成 "收件箱"
        os.rename(self.inbox, os.path.join(self.ws, "收件箱"))
        r = ds_intake.list_inbox(self.ds)
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["inbox"], "收件箱")
        # 一个候选都没有 → 诚实报错
        os.rename(os.path.join(self.ws, "收件箱"), os.path.join(self.ws, "别的"))
        r = ds_intake.list_inbox(self.ds)
        self.assertEqual(r.get("error"), "inbox_not_found")

    def test_08b_inbox_candidate_outside_root_rejected(self):
        """用户覆盖把 inboxDirs 指到工作区外 → 两道闸都要立得住:
        ① ../ 段在规则表加载期就整体降级(taxonomy_bad,GLM panel 建议);
        ② 万一有不带 .. 的越界形态(symlink 候选),_find_inbox within 闸兜底
        (subsense panel 建议)。列举面不外泄;写面本就被 stage_plan 拦。"""
        outside = tempfile.mkdtemp(prefix="dsintake-outside-")
        self.addCleanup(shutil.rmtree, outside, True)
        _write(os.path.join(outside, "秘密.txt"))
        os.rename(self.inbox, os.path.join(self.ws, "别的名字"))
        # ① .. 段:加载期拒
        rel = os.path.relpath(outside, self.ws)
        _write(os.path.join(self.ds, "config", "taxonomy.json"),
               json.dumps({"inboxDirs": [rel]}, ensure_ascii=False))
        r = ds_intake.list_inbox(self.ds)
        self.assertEqual(r.get("error"), "taxonomy_bad")
        # ② symlink 候选指向工作区外:名字合法但 realpath 越界 → within 闸拒
        os.symlink(outside, os.path.join(self.ws, "假收件箱"))
        _write(os.path.join(self.ds, "config", "taxonomy.json"),
               json.dumps({"inboxDirs": ["假收件箱"]}, ensure_ascii=False))
        r = ds_intake.list_inbox(self.ds)
        self.assertEqual(r.get("error"), "inbox_not_found")

    def test_08d_symlink_assignment_rejected(self):
        """指派一个 symlink 名(绕过 list_inbox 只是没列)→ stage 拒
        (与列举跳过对称;不然移走的是链接真身,MiMo panel 抓的不对称)。"""
        _write(os.path.join(self.inbox, "真文件.pdf"))
        os.symlink(os.path.join(self.inbox, "真文件.pdf"),
                   os.path.join(self.inbox, "链接.pdf"))
        r = ds_intake.stage_intake(
            [{"name": "链接.pdf", "project": PROJ_A, "category": "资料"}],
            self.allowed, ds_root=self.ds)
        self.assertEqual(r.get("error"), "file_not_in_inbox")

    def test_08c_symlink_entries_skipped(self):
        """收件箱里的 symlink(文件/目录)不认领:既不列出也不可 stage。"""
        target = os.path.join(self.ws, "01-项目", PROJ_A)
        os.symlink(target, os.path.join(self.inbox, "链接目录"))
        _write(os.path.join(self.inbox, "真文件.pdf"))
        os.symlink(os.path.join(self.inbox, "真文件.pdf"),
                   os.path.join(self.inbox, "链接文件.pdf"))
        r = ds_intake.list_inbox(self.ds)
        names = [e["name"] for e in r["entries"]]
        self.assertEqual(names, ["真文件.pdf"])

    def test_09_workspace_unconfigured(self):
        os.remove(os.path.join(self.ds, "config", "workspace.json"))
        r = ds_intake.list_inbox(self.ds)
        self.assertEqual(r.get("error"), "workspace_not_configured")

    def test_10_dotfiles_and_bad_names_skipped(self):
        _write(os.path.join(self.inbox, ".DS_Store"))
        _write(os.path.join(self.inbox, "正常.pdf"))
        r = ds_intake.list_inbox(self.ds)
        names = [e["name"] for e in r["entries"]]
        self.assertEqual(names, ["正常.pdf"])


class StageIntakeOracle(IntakeBase):
    def _stage(self, assignments):
        return ds_intake.stage_intake(assignments, self.allowed, ds_root=self.ds)

    def test_11_stage_project_scope(self):
        _write(os.path.join(self.inbox, "户型图.dwg"), "DWG")
        r = self._stage([{"name": "户型图.dwg", "project": PROJ_A, "category": "CAD"}])
        self.assertTrue(r.get("ok"), r)
        plan = self._load_plan(r["plan_id"])
        op = plan["operations"][0]
        self.assertEqual(op["src_rel"].replace("\\", "/"), "00-收件箱/户型图.dwg")
        self.assertEqual(op["dst_rel"].replace("\\", "/"),
                         f"01-项目/{PROJ_A}/03-CAD/户型图.dwg")
        # stage 零改动:文件还在收件箱
        self.assertTrue(os.path.exists(os.path.join(self.inbox, "户型图.dwg")))

    def test_12_stage_workspace_scope_ignores_project(self):
        _write(os.path.join(self.inbox, "参考.jpg"))
        r = self._stage([{"name": "参考.jpg", "project": None, "category": "参考图"}])
        self.assertTrue(r.get("ok"), r)
        plan = self._load_plan(r["plan_id"])
        self.assertEqual(plan["operations"][0]["dst_rel"].replace("\\", "/"),
                         "03-共享资源/参考图库/参考.jpg")

    def test_13_project_required_for_project_scope(self):
        _write(os.path.join(self.inbox, "户型图.dwg"))
        r = self._stage([{"name": "户型图.dwg", "project": None, "category": "CAD"}])
        self.assertEqual(r.get("error"), "project_required")

    def test_14_unknown_category_and_project(self):
        _write(os.path.join(self.inbox, "a.pdf"))
        r = self._stage([{"name": "a.pdf", "project": PROJ_A, "category": "不存在"}])
        self.assertEqual(r.get("error"), "unknown_category")
        r = self._stage([{"name": "a.pdf", "project": "不存在的项目", "category": "资料"}])
        self.assertEqual(r.get("error"), "project_not_found")

    def test_15_name_must_be_single_segment_in_inbox(self):
        _write(os.path.join(self.inbox, "a.pdf"))
        for bad in ("../外面.pdf", "子夹/内部.pdf", "不存在.pdf", "..", ""):
            r = self._stage([{"name": bad, "project": PROJ_A, "category": "资料"}])
            self.assertIn(r.get("error"),
                          ("bad_name", "file_not_in_inbox"), (bad, r))

    def test_16_dir_assignment_moves_whole_dir(self):
        sub = os.path.join(self.inbox, "业主一批图")
        os.makedirs(sub)
        _write(os.path.join(sub, "1.jpg"))
        r = self._stage([{"name": "业主一批图", "project": PROJ_A, "category": "资料"}])
        self.assertTrue(r.get("ok"), r)
        plan = self._load_plan(r["plan_id"])
        self.assertEqual(len(plan["operations"]), 1)  # 单个整夹 op,不递归拆散
        self.assertEqual(plan["operations"][0]["dst_rel"].replace("\\", "/"),
                         f"01-项目/{PROJ_A}/01-资料/业主一批图")

    def test_17_full_chain_approve_apply_moves_file(self):
        """端到端(核心层):stage → 人工 approve → apply → 文件真归位。"""
        _write(os.path.join(self.inbox, "参考.jpg"), "IMG")
        r = self._stage([{"name": "参考.jpg", "project": None, "category": "参考图"}])
        pid = r["plan_id"]
        self.assertTrue(ds_organize.approve_plan(pid, ds_root=self.ds).get("ok"))
        a = ds_organize.apply_plan(pid, self.allowed, ds_root=self.ds)
        self.assertTrue(a.get("ok"), a)
        dst = os.path.join(self.ws, "03-共享资源", "参考图库", "参考.jpg")
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(os.path.join(self.inbox, "参考.jpg")))

    def test_17b_apply_creates_missing_category_dir(self):
        """项目里还没有 03-CAD 夹:apply 建目录后落位(ds_organize 既有能力,
        钉住 intake 依赖它这一事实)。"""
        _write(os.path.join(self.inbox, "户型图.dwg"), "DWG")
        r = self._stage([{"name": "户型图.dwg", "project": PROJ_A, "category": "CAD"}])
        pid = r["plan_id"]
        ds_organize.approve_plan(pid, ds_root=self.ds)
        a = ds_organize.apply_plan(pid, self.allowed, ds_root=self.ds)
        self.assertTrue(a.get("ok"), a)
        self.assertTrue(os.path.exists(os.path.join(
            self.ws, "01-项目", PROJ_A, "03-CAD", "户型图.dwg")))

    def test_18_root_not_in_allowed_roots_honest_error(self):
        """工作区根不在 DS_ORGANIZE_ROOTS → stage_plan 的 root_not_allowed 原样透出
        (root⟂DS_ORGANIZE_ROOTS 不变量:不隐式打通,报错让人去配)。"""
        _write(os.path.join(self.inbox, "参考.jpg"))
        r = ds_intake.stage_intake(
            [{"name": "参考.jpg", "project": None, "category": "参考图"}],
            allowed_roots=["/nonexistent-other"], ds_root=self.ds)
        self.assertEqual(r.get("error"), "root_not_allowed")

    def test_19_empty_assignments(self):
        r = self._stage([])
        self.assertEqual(r.get("error"), "empty_plan")

    def _load_plan(self, plan_id):
        p = os.path.join(self.ds, "organize", "plans", f"plan_{plan_id}.json")
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)


class StageInboxAutoOracle(IntakeBase):
    """stage_inbox_auto:采纳"确定性建议"自动暂存。主 agent 拥有,执行腿 off-limits。
    规则:文件有类目 → 若类目 project 级需有唯一项目建议、workspace 级(参考图)无需项目;
    否则(未知扩展/歧义项目/目录)进 skipped 留人工。至少一条 → 过 stage_intake 落 plan。"""

    def test_confident_project_file_staged(self):
        # 龙腾世纪户型.pdf → 资料(auto,project 级)+ 唯一命中 PROJ_A → 自动暂存
        _write(os.path.join(self.inbox, "龙腾世纪户型.pdf"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertTrue(r["ok"])
        self.assertEqual(r["staged"], 1)
        self.assertIsNotNone(r["plan_id"])
        self.assertEqual(r["skipped"], [])

    def test_workspace_scope_needs_no_project(self):
        # 客厅参考.jpg → 参考图(workspace 级)→ 无需项目也自动暂存
        _write(os.path.join(self.inbox, "客厅参考.jpg"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 1)
        self.assertIsNotNone(r["plan_id"])

    def test_ambiguous_project_skipped(self):
        # 户型图.pdf:资料(auto,project 级)但文件名无项目 token → 歧义 → skipped 不进 plan
        _write(os.path.join(self.inbox, "户型图.pdf"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 0)
        self.assertIsNone(r["plan_id"])
        self.assertEqual([(s["name"], s["reason"]) for s in r["skipped"]],
                         [("户型图.pdf", "ambiguous_project")])

    def test_suggest_mode_never_auto_staged(self):
        # 四审回归:CAD/SU/MAX/PSD(mode=suggest 被引用类目)即使唯一命中项目也永不自动暂存,
        # 留 referenced_type 交人工(挪一动就断 xref/贴图链)。
        _write(os.path.join(self.inbox, "龙腾世纪平面.dwg"))   # CAD,唯一命中 PROJ_A
        _write(os.path.join(self.inbox, "龙腾世纪.skp"))       # SU
        _write(os.path.join(self.inbox, "龙腾世纪.max"))       # 3DMAX
        _write(os.path.join(self.inbox, "龙腾世纪.psd"))       # PS源
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 0)
        self.assertIsNone(r["plan_id"])
        self.assertEqual({s["reason"] for s in r["skipped"]}, {"referenced_type"})

    def test_unknown_ext_skipped(self):
        _write(os.path.join(self.inbox, "神秘.xyz"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 0)
        self.assertEqual(r["skipped"][0]["reason"], "unknown_type")

    def test_dir_skipped(self):
        os.makedirs(os.path.join(self.inbox, "一批图"))
        _write(os.path.join(self.inbox, "一批图", "a.jpg"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 0)
        self.assertEqual([(s["name"], s["reason"]) for s in r["skipped"]],
                         [("一批图", "not_a_file")])

    def test_mixed_batch(self):
        # 一把混合:2 确定(dwg+jpg)+ 2 skip(歧义 dwg + 未知 xyz)
        _write(os.path.join(self.inbox, "龙腾世纪立面.pdf"))   # 资料 → PROJ_A
        _write(os.path.join(self.inbox, "参考.png"))            # 参考图 → 参考图库
        _write(os.path.join(self.inbox, "平面.pdf"))            # 资料,歧义
        _write(os.path.join(self.inbox, "x.xyz"))              # 未知
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertEqual(r["staged"], 2)
        self.assertIsNotNone(r["plan_id"])
        self.assertEqual(sorted(s["name"] for s in r["skipped"]), ["x.xyz", "平面.pdf"])

    def test_nothing_confident(self):
        _write(os.path.join(self.inbox, "只有.xyz"))
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertTrue(r["ok"])
        self.assertEqual(r["staged"], 0)
        self.assertIsNone(r["plan_id"])

    def test_empty_inbox_ok(self):
        r = ds_intake.stage_inbox_auto(self.allowed, self.ds)
        self.assertTrue(r["ok"])
        self.assertEqual(r["staged"], 0)
        self.assertEqual(r["skipped"], [])

    def test_unconfigured_propagates(self):
        empty = tempfile.mkdtemp(prefix="dsintake-empty-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        r = ds_intake.stage_inbox_auto([empty], empty)
        self.assertEqual(r.get("error"), "workspace_not_configured")


class AmendPlanOracle(IntakeBase):
    """amend_plan:收件箱卡片单条纠偏(track opendesign-frontend-p1 design §②)。
    主 agent 拥有,执行腿 off-limits。契约:
    - drop = operations 下标列表(非空/全 int 且非 bool/无重复/在范围内)否则 bad_drop;
    - 剩余行经 stage_plan 全套复验重新暂存;stage 失败旧 plan 一字不动;
    - 成功(含剩余 0 行=整案取消)旧 plan 写 superseded_at + superseded_by,不删文件;
    - 已 applied / 已 superseded 的 plan 拒绝再纠偏。"""

    def _stage_two(self):
        _write(os.path.join(self.inbox, "客厅参考.jpg"), "IMG1")
        _write(os.path.join(self.inbox, "卧室参考.jpg"), "IMG2")
        r = ds_intake.stage_intake(
            [{"name": "客厅参考.jpg", "project": None, "category": "参考图"},
             {"name": "卧室参考.jpg", "project": None, "category": "参考图"}],
            self.allowed, ds_root=self.ds)
        self.assertTrue(r.get("ok"), r)
        return r["plan_id"]

    def _load_plan(self, plan_id):
        p = os.path.join(self.ds, "organize", "plans", f"plan_{plan_id}.json")
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)

    def _amend(self, plan_id, drop):
        return ds_intake.amend_plan(plan_id, drop, self.allowed, ds_root=self.ds)

    def test_a1_drop_one_restages_rest(self):
        pid = self._stage_two()
        r = self._amend(pid, [0])
        self.assertTrue(r.get("ok"), r)
        self.assertIsNotNone(r["plan_id"])
        self.assertNotEqual(r["plan_id"], pid)
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["dropped"], 1)
        # 新 plan = 被留下的那行(下标 1)
        new = self._load_plan(r["plan_id"])
        self.assertEqual(len(new["operations"]), 1)
        self.assertIn("卧室参考.jpg", new["operations"][0]["src_rel"])
        # 旧 plan 标记 superseded,指向新 plan;文件仍在(审计留痕)
        old = self._load_plan(pid)
        self.assertTrue(old.get("superseded_at"))
        self.assertEqual(old.get("superseded_by"), r["plan_id"])
        # 零改动:两个文件都还在收件箱
        self.assertTrue(os.path.exists(os.path.join(self.inbox, "客厅参考.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.inbox, "卧室参考.jpg")))

    def test_a2_drop_all_cancels(self):
        pid = self._stage_two()
        r = self._amend(pid, [1, 0])
        self.assertTrue(r.get("ok"), r)
        self.assertIsNone(r["plan_id"])
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["dropped"], 2)
        old = self._load_plan(pid)
        self.assertTrue(old.get("superseded_at"))
        self.assertIsNone(old.get("superseded_by"))

    def test_a3_bad_plan_id_and_not_found(self):
        self.assertEqual(self._amend("../走私", [0]).get("error"), "bad_plan_id")
        self.assertEqual(self._amend("20990101-000000-abcdef", [0]).get("error"),
                         "plan_not_found")

    def test_a4_bad_drop_rejected(self):
        pid = self._stage_two()
        for bad in ([], None, "0", [0.5], ["0"], [True], [2], [-1], [0, 0]):
            r = self._amend(pid, bad)
            self.assertEqual(r.get("error"), "bad_drop", (bad, r))
        # 全部拒掉之后 plan 原封不动(没被误 supersede)
        self.assertFalse(self._load_plan(pid).get("superseded_at"))

    def test_a5_applied_plan_refused(self):
        pid = self._stage_two()
        ds_organize.approve_plan(pid, ds_root=self.ds)
        a = ds_organize.apply_plan(pid, self.allowed, ds_root=self.ds)
        self.assertTrue(a.get("ok"), a)
        self.assertEqual(self._amend(pid, [0]).get("error"), "already_applied")

    def test_a6_superseded_plan_refused_again(self):
        pid = self._stage_two()
        self.assertTrue(self._amend(pid, [0, 1]).get("ok"))
        self.assertEqual(self._amend(pid, [0]).get("error"), "plan_superseded")

    def test_a7_stage_failure_keeps_old_plan(self):
        """留下的行 src 已消失 → stage_plan 复验拒(src_missing)→ 旧 plan 不动。"""
        pid = self._stage_two()
        os.remove(os.path.join(self.inbox, "卧室参考.jpg"))
        r = self._amend(pid, [0])  # 留下标 1(已被删)
        self.assertEqual(r.get("error"), "src_missing", r)
        old = self._load_plan(pid)
        self.assertFalse(old.get("superseded_at"))
        self.assertFalse(old.get("superseded_by"))

    def test_a9_malformed_plan_bad_plan_not_500(self):
        """畸形 plan(手工改坏:op 缺 src_rel / root 缺失)→ 干净 bad_plan,
        不抛 KeyError(四审三腿独立标的 500 面;核心契约=永远回 error dict)。"""
        pid = self._stage_two()
        path = os.path.join(self.ds, "organize", "plans", f"plan_{pid}.json")
        with open(path, encoding="utf-8") as fh:
            plan = json.load(fh)
        del plan["operations"][1]["src_rel"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False)
        r = self._amend(pid, [0])  # 留下标 1(畸形行)
        self.assertEqual(r.get("error"), "bad_plan", r)
        # root 整个缺失同样干净拒
        plan["operations"][1]["src_rel"] = "00-收件箱/卧室参考.jpg"
        del plan["root"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False)
        r = self._amend(pid, [0])
        self.assertEqual(r.get("error"), "bad_plan", r)

    def test_a10_amend_write_is_atomic_no_tmp_leftover(self):
        """supersede 写盘走 tmp+os.replace(subkimi M1 修):plans/ 下不残留
        .tmp,且旧 plan 重读仍是合法 JSON。"""
        pid = self._stage_two()
        self.assertTrue(self._amend(pid, [0]).get("ok"))
        plans = os.path.join(self.ds, "organize", "plans")
        self.assertEqual([f for f in os.listdir(plans) if f.endswith(".tmp")], [])
        self._load_plan(pid)  # 合法 JSON(坏了会抛)

    def test_a8_superseded_blocked_from_approve_and_apply(self):
        """废案在 ds_organize 两道闸也被拒:CLI ds-approve / MCP apply 都批不动。"""
        pid = self._stage_two()
        self.assertTrue(self._amend(pid, [0]).get("ok"))
        self.assertEqual(ds_organize.approve_plan(pid, ds_root=self.ds).get("error"),
                         "plan_superseded")
        # 就算 approve 标记被绕过手工写上,apply 仍拒
        marker = os.path.join(self.ds, "organize", "plans", f"plan_{pid}.approved")
        _write(marker, "2026-07-18 00:00:00\n")
        self.assertEqual(
            ds_organize.apply_plan(pid, self.allowed, ds_root=self.ds).get("error"),
            "plan_superseded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
