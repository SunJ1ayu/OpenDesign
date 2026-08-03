#!/usr/bin/env python3
"""design-studio 参考图 MCP 登记层。"""
from __future__ import annotations

import os

from ds_refs import (
    DEFAULT_DS_ROOT,
    add_ref,
    add_style,
    find_refs,
    link_ref,
    update_ref,
)


def build(ds_root: str | None = None):
    from mcp.server.fastmcp import FastMCP  # 延迟导入

    if ds_root is None:
        ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    server = FastMCP("design-studio-refs")

    @server.tool()
    def add_ref_tool(file: str, style: str, space: str, source: str = "",
                     note: str = "") -> dict:
        """登记一张参考图到索引。file=refs/ 下相对路径(文件须已存在);
        style/space 须在词表内(可逗号分隔多值);source 如 小红书/Pinterest/Behance。"""
        return add_ref(file, style, space, source, note, ds_root=ds_root)

    @server.tool()
    def find_refs_tool(style: str = "", space: str = "", project: str = "",
                       keyword: str = "") -> dict:
        """按风格/空间/用过的项目/关键词查参考图,条件 AND,全空=全量。"""
        return find_refs(style, space, project, keyword, ds_root=ds_root)

    @server.tool()
    def link_ref_tool(ref_id: str, project: str) -> dict:
        """记录某张参考图(r<n>)用在了某个项目。"""
        return link_ref(ref_id, project, ds_root=ds_root)

    @server.tool()
    def add_style_tool(style: str) -> dict:
        """往风格词表新增一个风格。新增前必须先跟设计师确认过。"""
        return add_style(style, ds_root=ds_root)

    @server.tool()
    def update_ref_tool(ref_id: str, style: str = "", space: str = "",
                        note: str | None = None) -> dict:
        """就地改一条已登记参考图(r<n>)的风格/空间/备注。三者都不传则报 no_fields
        (不接受只 bump 页脚的假写);style/space 给了必须在词表内(可逗号分隔多值,
        不自动建词);note 传空串会清空备注。没点名的字段(含来源/文件/用于)不动。"""
        return update_ref(ref_id, style=style or None, space=space or None,
                          note=note, ds_root=ds_root)

    return server
