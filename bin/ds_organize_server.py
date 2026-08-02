#!/usr/bin/env python3
"""design-studio 文件整理 MCP 登记层。"""
from __future__ import annotations

import os

import ds_adopt
import ds_intake
from ds_organize import DEFAULT_DS_ROOT, apply_plan, scan_dir, stage_plan


def build(ds_root: str | None = None, allowed_roots: list[str] | None = None):
    from mcp.server.fastmcp import FastMCP  # 延迟导入

    if ds_root is None:
        ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    if allowed_roots is None:
        # os.pathsep:Linux 冒号 / Windows 分号(Windows 路径自带盘符冒号,不能拿冒号切)
        allowed_roots = [p for p in os.environ.get("DS_ORGANIZE_ROOTS", "").split(os.pathsep)
                         if p]
    server = FastMCP("design-studio-organize")

    @server.tool()
    def scan_dir_tool(root: str) -> dict:
        """整理文件夹的第一步:设计师说"帮我整理/归类这个文件夹/批量改名/归档旧文件"
        时先调这个——只读列出 root 下的文件/子目录(相对路径、类型、大小、修改时间),
        看清现状再 stage_plan 出方案。本身零改动,放心调。"""
        return scan_dir(root, allowed_roots=allowed_roots)

    @server.tool()
    def stage_plan_tool(root: str, operations: list[dict]) -> dict:
        """暂存一份整理方案(零改动)。operations=[{op: move|rename, src, dst}],
        路径相对 root。返回 plan_id + 给人看的清单;需用户在终端 ds-approve 批准。"""
        return stage_plan(root, operations, allowed_roots=allowed_roots,
                          ds_root=ds_root)

    @server.tool()
    def apply_plan_tool(plan_id: str) -> dict:
        """执行一份已经人工批准的方案。未批准会被拒绝——请用户在终端跑
        `ds-approve <plan_id>`,聊天里说"确认"不算数。"""
        return apply_plan(plan_id, allowed_roots=allowed_roots, ds_root=ds_root)

    @server.tool()
    def list_inbox_tool() -> dict:
        """看收件箱:设计师问"收件箱里有什么/有没有新文件/帮我整理收件箱"时先调
        这个——列出工作区 00-收件箱 里的文件,带确定性建议(扩展名→类目,文件名
        含项目名→建议项目;歧义留空,要问用户别猜)。只读零改动,放心调。"""
        return ds_intake.list_inbox(ds_root)

    @server.tool()
    def stage_intake_tool(assignments: list[dict]) -> dict:
        """把收件箱文件的归类指派暂存成方案(零改动):设计师确认了"这个文件归
        哪个项目哪个类目"之后调用。assignments=[{name: 收件箱内文件名,
        project: 项目名(参考图等工作区级类目可为 null), category: 类目 id}]。
        返回 plan_id;真正移动要用户在工作台收件箱卡片点「确认执行」,
        聊天里说"确认"不算数,也不要自己调 apply_plan_tool 替用户确认。"""
        return ds_intake.stage_intake(assignments, allowed_roots=allowed_roots,
                                      ds_root=ds_root)

    @server.tool()
    def adopt_workspace_tool() -> dict:
        """接管我的工作区 / 盘点工作区 / 首装 / 看看工作区什么情况 / 采纳现状:
        一次只读盘点整个工作区——识别收件箱/项目根/归档/共享结构,列出每个项目夹的
        绑定状态、类目、根层散文件数,以及有档案却没绑文件夹的项目。零改动。据此
        引导设计师逐个 bind_project,再对项目内散文件调 stage_adoption。"""
        return ds_adopt.adopt_scan(ds_root)

    @server.tool()
    def stage_adoption_tool(project_key: str) -> dict:
        """把某个已绑定项目【项目夹根一层】的散文件按 taxonomy 暂存归位(零改动):
        auto 类目(资料/参考图)进方案,suggest 类目(CAD/SU/MAX/PSD 被引用风险)
        只在 advice 里口头建议、永不自动动,未知扩展名进 skipped。返回 plan_id;
        真正移动要设计师在工作台卡片点「确认执行」,你不能替他确认也别自己调
        apply_plan_tool。"""
        return ds_adopt.stage_adoption(project_key, allowed_roots=allowed_roots,
                                       ds_root=ds_root)

    return server
