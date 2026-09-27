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
// ⇒ 必须按**这张卡归哪个聊天**判断。
//
// ## 归属的真实信号:工具的"开始"事件(PR #3 审查)
// 以前按"卡冒出来时哪几个聊天在跑"猜 —— 两个聊天同时在跑时就把两个都算成主人,
// 项目助手在等自己的卡时,首页再提一张,切到项目页仍能看到首页的卡。
// 网关开了 sendToolHints(ds_shell_core.patch_config 写)后,每次调用工具**之前**会往
// **发起它的那条聊天连接**推一条 tool_hint,带 phase:"start"、工具名和参数。
// 于是每个聊天记下"我发起了哪些还没结束的受闸调用(动作 + 参数)",卡片冒出来时按
// 动作 + 参数对上是谁发起的 —— 这是事实,不是猜。收不到这条信号(老配置)才退回按"谁在跑"。

/** 受闸工具名 → 同意卡上的动作名(与 bin/ds_consent.py GUARDED_ACTIONS 一致)。 */
export function consentActionOf(toolName: unknown): "set_workspace" | "bind_project" | null {
  if (typeof toolName !== "string") return null;
  if (toolName.endsWith("set_workspace_tool")) return "set_workspace";
  if (toolName.endsWith("bind_project_tool")) return "bind_project";
  return null;
}

/** 卡片(来自 /api/consent)的最小形状。 */
export type ConsentCardRef = { pending_id: string; action?: string; params?: Record<string, unknown> };

type OpenCall = { slot: string; turn: number; action: string; args: Record<string, unknown> };

/** 路径比较:Windows 不分大小写、正反斜杠都认、忽略末尾分隔符。后端记的是 realpath,
 *  助手传的是原样路径 —— 对不上时退回"同动作的唯一发起者",不会因此认错主。 */
function samePath(a: unknown, b: unknown): boolean {
  const n = (x: unknown) =>
    typeof x === "string" ? x.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase() : null;
  const na = n(a);
  return na !== null && na === n(b);
}

/** 文件夹比较:卡上记的是后端解析后的 key(按年份/客户分组时形如 `2026:甲`),助手传的可能是
 *  纯名(`甲`,后端唯一命中才会绑)。所以全名相同,或卡上的是 `分组:助手说的纯名`,都算同一个。 */
function sameFolder(asked: unknown, recorded: unknown): boolean {
  if (typeof asked !== "string" || typeof recorded !== "string") return false;
  return asked === recorded || (recorded.includes(":") && recorded.split(":", 2)[1] === asked);
}

function argsMatch(action: string, args: Record<string, unknown>, params: Record<string, unknown>): boolean {
  if (action === "set_workspace") return samePath(args.root, params.root);
  // 项目名**和**文件夹都要对上(PR #3 二审:只比项目名时,两个聊天把同一个项目绑到不同文件夹,
  // 两张卡都认两个聊天为主,项目页里看得到首页那张)
  if (action === "bind_project") {
    return args.project === params.project && sameFolder(args.folder, params.folder);
  }
  return false;
}

export class ConsentOwners {
  /** 正在跑的聊天 → 它当前这一轮的编号。 */
  private busy = new Map<string, number>();
  /** 每个聊天跑过几轮(只增不减):同一个聊天停了又开新一轮,编号不同 ⇒ 不是同一轮。 */
  private turns = new Map<string, number>();
  /** 每张卡的主人:发起它的那几**轮**(slot → 轮次)。空 = 不知道是谁。 */
  private owners = new Map<string, Map<string, number>>();
  /** 还没结束的受闸工具调用(call_id → 谁发起、第几轮、动作、参数),来自工具"开始"事件。 */
  private open = new Map<string, OpenCall>();
  /** 已经认领过一张卡的调用:一次调用只排一张卡,认过就不许再被别的卡拿去当主人。 */
  private claimed = new Set<string>();

  /** 某个聊天的连接里收到受闸工具的"开始"事件。 */
  toolStarted(slot: string, callId: string, action: string, args: Record<string, unknown>): void {
    const turn = this.busy.get(slot) ?? this.turns.get(slot) ?? 0;
    this.open.set(`${slot}#${callId}`, { slot, turn, action, args });
  }

  /** 收到"结束"事件,或这一轮结束 / 被停止:这次调用不再算"还开着"。 */
  toolEnded(slot: string, callId: string): void {
    this.open.delete(`${slot}#${callId}`);
    this.claimed.delete(`${slot}#${callId}`);
  }

  setBusy(slot: string, on: boolean): void {
    if (on) {
      const turn = (this.turns.get(slot) ?? 0) + 1;
      this.turns.set(slot, turn);
      this.busy.set(slot, turn);
    } else {
      this.busy.delete(slot);
      // 这一轮结束 / 被停止:它发起的调用都不再"开着"(已认过主的卡不受影响)
      for (const [k, c] of this.open) {
        if (c.slot === slot) {
          this.open.delete(k);
          this.claimed.delete(k);
        }
      }
    }
  }

  anyBusy(): boolean {
    return this.busy.size > 0;
  }

  /**
   * 每次拉到卡片列表时调用:新卡认主,已消失的卡清掉。认主顺序(只看**还没认领过卡**的调用):
   *  ① 同动作、参数对得上(动作 + 全部关键参数)的调用 ⇒ 它们的聊天;
   *  ② 参数都对不上(写法差异等),但同动作的调用只剩**一个** ⇒ 就是它;
   *  ③ 同动作的调用有好几个、参数又都对不上 ⇒ 分不清,全算上(宁可多显示,也不能让卡没处点);
   *  ④ 一个都没有(网关没开 sendToolHints 的老配置)⇒ 退回"此刻在跑的那几轮"。
   */
  observe(cards: readonly (ConsentCardRef | string)[]): void {
    const list = cards.map((c) => (typeof c === "string" ? { pending_id: c } : c));
    const live = new Set(list.map((c) => c.pending_id));
    for (const id of [...this.owners.keys()]) if (!live.has(id)) this.owners.delete(id);
    for (const c of list) {
      if (this.owners.has(c.pending_id)) continue;
      const same = [...this.open.entries()]
        .filter(([k, o]) => o.action === c.action && !this.claimed.has(k));
      const exact = same.filter(([, o]) => argsMatch(o.action, o.args, c.params ?? {}));
      const from = exact.length ? exact : same;
      if (from.length === 0) {
        this.owners.set(c.pending_id, new Map(this.busy));
        continue;
      }
      if (exact.length || same.length === 1) for (const [k] of from) this.claimed.add(k);
      this.owners.set(c.pending_id, new Map(from.map(([, o]) => [o.slot, o.turn] as [string, number])));
    }
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

  /**
   * 这张卡该在哪个聊天里显示(照 ZCode:确认窗属于提它的那个会话,切走就不在别处出现)。
   * 业主反馈:卡片跳出来后切到别的页面,卡也跟着一直在 —— 以前是"哪个聊天在屏幕上就显示在哪"。
   * 归属不明(看见时没有聊天在跑,比如刚打开软件时就已经排着的旧卡)⇒ 哪个聊天都显示,
   * 免得卡片没地方点、一直挂着。
   */
  showsIn(id: string, slot: string): boolean {
    const own = this.owners.get(id);
    return !own || own.size === 0 || own.has(slot);
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
