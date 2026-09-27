// 业主同意卡的数据源(track opendesign-consent-dock)——三个聊天实例共用一份。
//
// 为什么是一份全局 store 而不是每张卡自己拉:三个 ChatPage(首页 / 项目助手 / 待办页)
// 常驻挂载,各拉各的就是三倍请求;更要紧的是**"要不要快拉"取决于任意一个聊天在不在跑**——
// 在首页发的话、切到工作区去看,助手的工具正停在那里等业主点,卡必须在**眼前这个**聊天里出来。
//
// 节拍:
//   · 有任何一个聊天在跑(busy)→ 每秒拉一次:助手一提请求,卡片一秒内出现(照 ZCode,不等这一轮结束);
//   · 都闲着但还有待确认 → 5 秒一次:别的窗口点掉了,这里跟着消失;
//   · 都闲着且没有待确认 → 不拉。另外挂载 / 切到可见 / 窗口回到前台 / 每轮结束时各拉一次。
import { useEffect, useSyncExternalStore } from "react";
import { fetchConsent, type ConsentPending } from "../api";
import { ConsentOwners, consentActionOf } from "./consentNotice";

const EMPTY: ConsentPending[] = [];
const FAST_MS = 1000;
const SLOW_MS = 5000;

let pending: ConsentPending[] = EMPTY;
const listeners = new Set<() => void>();
let inflight = false;
// 哪些聊天在跑 + 每张卡归哪个聊天(见 consentNotice.ts 顶部的第一性说明)。
const owners = new ConsentOwners();
let timer: ReturnType<typeof setInterval> | undefined;
let timerMs = 0;

function sameList(a: ConsentPending[], b: ConsentPending[]): boolean {
  return a.length === b.length && a.every((p, i) => p.pending_id === b[i].pending_id);
}

function publish(next: ConsentPending[]) {
  if (sameList(next, pending)) return;
  pending = next.length ? next : EMPTY;
  listeners.forEach((l) => l());
  retime();
}

function retime() {
  const want = owners.anyBusy() ? FAST_MS : pending.length > 0 ? SLOW_MS : 0;
  if (want === timerMs) return;
  if (timer !== undefined) clearInterval(timer);
  timer = want ? setInterval(refreshConsent, want) : undefined;
  timerMs = want;
}

/** 业主点完之后,结果是否已作为工具返回值送到了**提这张卡的那一轮**(见 ConsentOwners.delivered)。 */
export function consentDelivered(pendingId: string, waiter: boolean | undefined): boolean {
  return owners.delivered(pendingId, waiter);
}

// 没送到时替业主说的那句话,要说给**提卡的那个聊天**(是它的助手在等)。
// 每个 ChatPage 按自己的 slot 登记一个"说一句"的函数:能发出去回 true。
const noticeHandlers = new Map<string, (text: string) => boolean>();

export function registerConsentNotice(slot: string, fn: (text: string) => boolean): () => void {
  noticeHandlers.set(slot, fn);
  return () => {
    if (noticeHandlers.get(slot) === fn) noticeHandlers.delete(slot);
  };
}

/** 先交给提卡的聊天;它发不出去(没连上 / 又在跑别的)就退回业主点卡的这个聊天(clickedFallback)。 */
export function deliverConsentNotice(pendingId: string, clickedSlot: string, text: string,
                                     clickedFallback: (text: string) => void): void {
  const target = owners.target(pendingId, clickedSlot);
  if (target !== clickedSlot && noticeHandlers.get(target)?.(text)) return;
  clickedFallback(text);
}

/**
 * 某个聊天的连接里收到一帧:从里面挑出受闸工具的"开始 / 结束"事件记账(认主的真实信号)。
 * 网关开了 sendToolHints 才会有"开始"事件(ds_shell_core.patch_config);没有也不出错,
 * 认主退回按"谁在跑"。
 */
export function noteConsentToolEvents(slot: string, frame: unknown): void {
  if (typeof frame !== "object" || frame === null) return;
  const events = (frame as { tool_events?: unknown }).tool_events;
  if (!Array.isArray(events)) return;
  let started = false;
  for (const ev of events) {
    if (typeof ev !== "object" || ev === null) continue;
    const e = ev as { phase?: unknown; call_id?: unknown; name?: unknown; arguments?: unknown };
    const action = consentActionOf(e.name);
    if (!action || typeof e.call_id !== "string") continue;
    if (e.phase === "start") {
      const args = typeof e.arguments === "object" && e.arguments !== null
        ? (e.arguments as Record<string, unknown>) : {};
      owners.toolStarted(slot, e.call_id, action, args);
      started = true;
    } else if (e.phase === "end") {
      owners.toolEnded(slot, e.call_id);
    }
  }
  if (started) refreshConsent(); // 卡马上就要冒出来了,别等下一拍轮询
}

/** 立刻拉一次(并发时合并成一次)。 */
export function refreshConsent(): void {
  if (inflight) return;
  inflight = true;
  fetchConsent()
    .then((s) => {
      const list = s.pending || [];
      owners.observe(list); // 新卡认主:按发起它的那次工具调用(见 ConsentOwners.observe)
      publish(list);
    })
    // 拉不到就当没有待确认:这张卡是**加法**,它自己坏掉不该把聊天带塌。
    // (真正的安全保证在后端 —— 拉不到卡不等于闸失效,那边照样不落盘。)
    .catch(() => publish(EMPTY))
    .finally(() => {
      inflight = false;
    });
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

/**
 * 当前待确认列表。
 * @param active 这个聊天此刻在屏幕上 —— 只有它渲染卡片(三个实例同时渲染会出三张)。
 * @param busy   这个聊天正在跑一轮 —— 哪怕它被藏起来了,也要让全局切到快拉。
 * @param slot   这个聊天的稳定身份(home / workspace / todo),用来记卡片归属。
 */
export function useConsentPending(active: boolean, busy: boolean, slot: string): ConsentPending[] {
  const list = useSyncExternalStore(subscribe, () => pending);

  useEffect(() => {
    if (!busy) return;
    owners.setBusy(slot, true);
    retime();
    refreshConsent();
    return () => {
      owners.setBusy(slot, false); // 结束或被 ■ 停止:它提的卡从此"没人接"
      retime();
      refreshConsent(); // 这一轮结束了:卡可能刚被点掉,也可能等超时还留着
    };
  }, [busy, slot]);

  useEffect(() => {
    if (!active) return;
    refreshConsent();
    const onFocus = () => refreshConsent();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [active]);

  if (!active) return EMPTY;
  // 只显示**本聊天提的**卡(归属不明的哪都显示),见 ConsentOwners.showsIn。
  const mine = list.filter((p) => owners.showsIn(p.pending_id, slot));
  return mine.length === list.length ? list : mine;
}
