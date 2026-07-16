# Proposal: opendesign-connect-ux

- Date: 2026-07-16
- Status: open

## Goal

修掉 07-16 用户真机撞出的三个交互断层:①「接入工作区」点了以为接了(实际只预填半句话);
②助手思考时零信号("在想"和"没理我"不可区分);③folder_count=0 后助手自由发挥、
问一堆才收敛。

## Motivation

三个都是实证(用户当天原话:"点接入工作区,然后说话没理我"),且都挡在"开始真实使用"
的路径上。产品策略=先修有实证的交互,功能侧(#7 驾驶舱)暂停到真实使用反馈回来。

## Scope

- in: CompanionColumn 接入区改成"点开→填路径→确认即发送"的完整动作
- in: ChatPage 新增 dispatch 原语(程序化发送,失败优雅降级为预填)+ 思考中指示
- in: workspace/AGENTS.md folder_count=0 话术收敛为一个二选一问题
- in: oracle + build + VERSION 0.15.0

## Non-goals

- 不做浏览器直连 set_workspace 的写端点(405 铁律不破,写只走 MCP=对话)
- 不改 LLM 回复速度本身(只修感知)
- 不动登录/连接/节流缓冲既有代码路径
