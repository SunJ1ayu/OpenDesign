# Proposal: opendesign-workbench-p5

- Date: 2026-07-12
- Status: open
- Base-ref: c2fbe45

## Goal

把用户真实文件工作区(按 docs/workspace-taxonomy.md v1.0 结构)以**只读窗口**接进
浏览器工作台:图墙(一等面)+ 项目文件概览(按类目统计+最近文件)+ "打开项目文件夹"
按钮(白名单 open-folder 端点,ds-web 只读铁律的唯一受控例外)。

## Motivation

07-08 定调:前端是项目工作区不是聊天软件,图墙=一等面,文件整理是日常价值本体;
07-12 目录结构 v1.0 定稿(=首装采纳标准),schema 输入已齐;用户拍板"概览+直达,
不做浏览器文件管理器",并选定 open-folder 端点方案(拒了复制路径保守版)。

## Scope

- in: 工作区根配置 + 项目→文件夹映射(不动 PKB schema)
- in: ds_web 只读端点:文件概览(类目计数+最近文件)、项目图片列表、项目图片静态服务
  (复用 refs 三闸模式)
- in: open-folder 端点(POST 受控例外:字符集/realpath within/目录存在三闸,
  无 shell,oracle red-check)
- in: 前端:2a 文件列真数据(概览+打开按钮)、图墙(空间/风格筛+大图)
- in: 按 taxonomy v1.0 的测试夹具样例树 + e2e 真 gateway

## Non-goals

- 归类引擎/收件箱认领 UI(下一 track;确认流 v1 走聊天 + ds-approve 已有闸)
- PKB 迁进工作区(项目档案.md 仍在 DS_ROOT/projects/,只加映射;迁移另 track)
- 文件树浏览/拖拽/重命名/删除(明确不做,资源管理器的活)
- 缩略图生成(v1 直出原图;性能问题真实出现再做)
- 效果图↔变更记录深度联动(先把图挂上墙)
