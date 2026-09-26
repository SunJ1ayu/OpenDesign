// 业主点完同意卡之后,要不要在对话里替业主告诉助手结果(track opendesign-consent-dock)。
// 纯函数、零依赖:判据(tests/test_consent_notice.mjs)用 Node 直接跑。

/**
 * 只有**同时**满足两条,结果才已经送到了助手手上、前端该闭嘴:
 *  ① 后端说有一次工具调用正停在这张卡上等(resolve 回执的 `waiter`);
 *  ② 此刻确实有一个聊天在跑一轮 —— 工具的返回值要有一轮对话来接。
 *
 * 只看 ① 不够(PR #2 本地审查实机抓到的 P2):业主点了 ■ 停止,网关把这一轮取消了,
 * 但 nanobot **不把取消传给 MCP 进程**,那次工具调用还在傻等、`waiter` 还是 true。
 * 业主再点「同意」,结果交给了一个没人接的工具,助手永远不知道。
 * 停止之后就没有聊天在跑了 ⇒ ② 不成立 ⇒ 照常告诉助手。
 *
 * 宁可多说一句(最坏:助手听到两遍同一个结果),不能少说(最坏:对话卡死、业主不知道为什么)。
 */
export function shouldTellAssistant(waiter: boolean | undefined, anyChatBusy: boolean): boolean {
  return !(waiter === true && anyChatBusy);
}

/** 替业主说的那句话。只是**告知**,不是授权 —— 授权在点卡片那一下已经完成。 */
export function consentNoticeText(title: string, approve: boolean): string {
  return approve
    ? `我在确认卡上点了「同意」(${title}),已经生效了,接着做吧。`
    : `我在确认卡上点了「拒绝」(${title}),先别改。`;
}
