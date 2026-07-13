# Proposal: opendesign-workbench-p6

- Date: 2026-07-13
- Status: open

## Goal

历史对话真正可用:侧栏点开任一历史对话 = 回放历史消息并**继续聊**(非只读);
每轮回复结束后会话列表自动出现/更新,不再要求 F5。

## Motivation

07-13 公司电脑首装真机反馈(用户原话):聊了一次,①侧栏历史对话不出现(要 F5),
②刷新出现后**点不动**。排查:`Sidebar.tsx` hist-row 是没有 onClick 的死按钮
(p3 有意留白,"全部"也标着"即将支持");会话列表只在页面加载/WS 连接时拉取。
对用户来说这俩加起来 = "历史对话功能是假的"。

底层已核全部就位,零后端改动:
- nanobot ws `attach` 信封(`channels/websocket.py:675`)原生支持挂回旧 chat_id
  续聊(会话 key = `websocket:<chat_id>`);
- ds_web 已代理 `/api/chat/sessions/<key>/thread` → `webui-thread`(proxy 有测试),
  返回历史消息供回放。

## Scope

- in: 点历史行 → 首页聊天 attach 续聊 + thread 回放;turn_end 自动刷新会话列表;
  e2e 真 gateway 断言(回放 + 续聊归同一会话);VERSION 0.7.0 + dist 重建。

## Non-goals

- "全部对话"完整列表页(保持"即将支持",侧栏仍最近 2 条)
- 对话删除/改名/搜索
