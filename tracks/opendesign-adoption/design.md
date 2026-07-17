# Design: opendesign-adoption

## 核心判断

地基已厚:类目"照现状认"早已成立(ds_workspace 把项目夹下一级目录当类目,不校验命名),
项目发现/绑定(候选目录名+显式映射+直名+token)、认领规则表(taxonomy.default.json,
auto/suggest 分级)、确认闸(stage_plan/.approved/卡片针孔④)全部现成。
**采纳引擎 v1 = 一层薄薄的"盘点+批量引导"胶水,不是新系统。**

## 关键决策

1. **报告型工具,不是状态机**:adopt_scan 每次全量重算,无持久"采纳状态"。
   绑定的持久化 = 既有 workspace.json 映射(bind_project 写);类目的持久化 = 不需要
   (照现状认 = 目录本身就是真相)。首装扫描和日常复扫是同一个工具。
2. **建议只覆盖项目根散文件**(镜像 intake 认领语义):auto 类目(资料/参考图)→ 暂存
   进 plan;suggest 类目(CAD/SU/MAX/PSD)→ advice 列表(口头),存量文件引用风险
   不可知,比 intake 还保守一档;未知扩展名 → skipped 列表(诚实)。
   scope=workspace 的类目(参考图库)dst 在工作区级共享夹 —— stage_plan root 用
   工作区根、ops 用相对路径即可覆盖(复核:plan root=项目夹时 dst 出不了夹,故
   **plan root = 工作区根**,src/dst 都相对工作区根;approve 针孔与 allowed_roots
   语义不变)。
3. **零 web 改动**:_pending_plans 列"root 在工作区根内且未 applied"的一切 plan,
   approve 针孔同域——采纳 plan 天然上卡片。e2e 只需证一次。
4. **结构识别 = 候选名单机制复用**:inbox 用 taxonomy.inboxDirs(已有);
   archive/shared 增加 archiveDirs/sharedDirs 键进 taxonomy.default.json(additive,
   用户 taxonomy.json 可覆盖);projects_root 用 ds_workspace 既有候选逻辑。
5. **未绑定双向都报**:文件夹无 PKB 档案(建档/绑定引导)+ PKB 档案无文件夹
   (可能改名/归档了,提示 bind_project 或忽略)。

## 数据形状(oracle 钉死的部分)

adopt_scan(ds_root) →
- 未配置: {"ok": True, "configured": False}
- 已配置: {"ok": True, "configured": True,
   "structure": {"inbox": rel|null, "projects_root": rel|null,
                  "archive": rel|null, "shared": rel|null},
   "projects": [{"folder", "bound": bool, "key": str|null,
                  "categories": [names], "loose_files": int}...],
   "unbound_pkb": [keys]}

stage_adoption(project_key) →
- 成功: {"ok": True, "plan_id", "staged": [...], "advice": [...], "skipped": [...]}
- 无可暂存: {"error": "nothing_to_stage", "advice": [...], "skipped": [...]}
- 未绑定/未配置: {"error": "project_not_bound"} / {"error": "workspace_not_configured"}

## 安全不变量(全部继承,零新增面)

写路径唯一 = 既有 stage_plan(root 必在 allowed_roots,.approved 只能人批);
adopt_scan/adopt_workspace 纯只读;root⟂DS_ORGANIZE_ROOTS 语义不变;
suggest 类目连 plan 都不进。
