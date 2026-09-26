// 业主点完同意卡之后,结果有没有送到助手手上、没送到该告诉哪个聊天(track opendesign-consent-dock)。
// 纯逻辑、零依赖:判据(tests/test_consent_notice.mjs)用 Node 直接跑。
//
// ## 第一性:结果要送到**提这张卡的那一轮对话**
// 工具停在卡上等(ds_tools_server.await_owner),业主点完,结果作为工具返回值交给助手 ——
// 前提是**提卡的那一轮还活着**。业主点了 ■ 停止,网关取消了那一轮,但 nanobot 不把取消传给
// MCP 进程:工具还在等、后端还报 waiter=true,可结果已经没人接了。
//
// 两轮审查的教训(PR #2):
//   · 第一版只看后端 waiter —— 点了停止之后 waiter 还是 true ⇒ 吞掉结果;
//   · 第二版看"waiter 且**任意**聊天在跑" —— 首页停止、项目助手在跑别的事时,仍被当成"有人接"⇒ 又吞掉。
// ⇒ 必须按**这张卡归哪个聊天**判断。前端能知道的最直接事实是:卡是在哪个聊天跑着的时候冒出来的
//   (聊天在跑时每秒拉一次卡片,卡一出现就记下当时在跑的那几个聊天)。

export class ConsentOwners {
  /** 正在跑的聊天 → 它当前这一轮的编号。 */
  private busy = new Map<string, number>();
  /** 每个聊天跑过几轮(只增不减):同一个聊天停了又开新一轮,编号不同 ⇒ 不是同一轮。 */
  private turns = new Map<string, number>();
  /** 每张卡第一次被看见时,正在跑的那几**轮**(slot → 轮次)。空 = 看见时没有聊天在跑。 */
  private owners = new Map<string, Map<string, number>>();

  setBusy(slot: string, on: boolean): void {
    if (on) {
      const turn = (this.turns.get(slot) ?? 0) + 1;
      this.turns.set(slot, turn);
      this.busy.set(slot, turn);
    } else {
      this.busy.delete(slot);
    }
  }

  anyBusy(): boolean {
    return this.busy.size > 0;
  }

  /** 每次拉到卡片列表时调用:新卡记下此刻在跑的那几轮,已消失的卡清掉。 */
  observe(ids: readonly string[]): void {
    const live = new Set(ids);
    for (const id of [...this.owners.keys()]) if (!live.has(id)) this.owners.delete(id);
    for (const id of ids) if (!this.owners.has(id)) this.owners.set(id, new Map(this.busy));
  }

  /**
   * 结果是不是已经作为工具返回值送到了助手手上(= 前端该闭嘴)。两条都要成立:
   *  ① 后端说有工具停在这张卡上等(resolve 回执的 waiter);
   *  ② **提这张卡的那一轮**此刻还在跑 —— 不只是同一个聊天:三审实机复现过
   *     "首页提 A → 停止 → 首页又提 B → 点 A 的旧卡",首页在跑的是 B 那一轮,A 的结果没人接。
   * 归属不明(看见时没有聊天在跑)⇒ 当作没人接。卡冒出来时恰好有几轮同时在跑 ⇒ 分不清是谁提的,
   * 要它们**全都**还在跑才算送到(用 some 的话,真正提卡的那一轮被停了、另一轮还在跑,就又吞掉了)。
   * 宁可多说一句(最坏:助手听到两遍),不能少说(最坏:对话卡死、业主不知道为什么)。
   */
  delivered(id: string, waiter: boolean | undefined): boolean {
    if (waiter !== true) return false;
    const own = this.owners.get(id);
    return !!own && own.size > 0 && [...own].every(([slot, turn]) => this.busy.get(slot) === turn);
  }

  /** 没送到时,告诉哪个聊天:归属唯一 ⇒ 提卡的那个聊天(是它的助手在等);否则 ⇒ 业主点卡的这个。 */
  target(id: string, clickedSlot: string): string {
    const own = this.owners.get(id);
    return own && own.size === 1 ? [...own.keys()][0] : clickedSlot;
  }
}

/**
 * 替业主说的那句话。只是**告知**,不是授权 —— 授权在点卡片那一下已经完成。
 * 同意时必须带上**落盘后的事实**并明说"已经生效、别再申请":PR #2 三审实机里,补话只说
 * "我点了同意",助手以为还没办,拿同样参数又调了一遍工具、又弹一张卡,也没报认出几个项目夹。
 */
export function consentNoticeText(title: string, approve: boolean,
                                  result?: Record<string, unknown>): string {
  if (!approve) return `我在确认卡上点了「拒绝」(${title}),什么都没改。先别再申请,问问我想怎么办。`;
  const r = result ?? {};
  let fact = "";
  if (typeof r.root === "string") {
    fact = typeof r.folder_count === "number"
      ? `工作区已经接到 ${r.root},认出 ${r.folder_count} 个项目夹`
      : `工作区已经接到 ${r.root}`;
  } else if (typeof r.project === "string" && typeof r.folder === "string") {
    fact = `项目「${r.project}」已经关联到文件夹「${r.folder}」`;
  }
  const done = "已经生效,不用再调用工具、也不用重新申请,直接接着做。";
  return fact
    ? `我在确认卡上点了「同意」:${fact}。${done}`
    : `我在确认卡上点了「同意」(${title}),${done}`;
}
