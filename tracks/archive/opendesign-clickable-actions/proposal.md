# Proposal: opendesign-clickable-actions (P0-1/2)

真机反馈"很多动作要回聊天太麻烦,该能直接点"。四审+主审合并排序(docs/frontend-actions-roadmap.md)。
本 track 做 P0 前两项(最高频×最便宜):①变更记录行内"+记一条";②未建档文件夹一键建档。
均为只读墙上受控写针孔,复用现有 ds_tools 核心(append_change/create_project),照 /api/changes/edit
先例。#3 收件箱扫描按钮需新核心函数(stage from suggestions),留下一 track。
