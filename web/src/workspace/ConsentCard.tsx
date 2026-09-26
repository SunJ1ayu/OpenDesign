import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import type { ConsentPending, ConsentResolved } from "../api";
import { resolveConsent } from "../api";
import { refreshConsent } from "../chat/consentStore";

// 业主同意卡(track opendesign-owner-consent)。
//
// 照 ZCode 挪到**聊天输入框正上方**(track opendesign-consent-dock):
// 以前它住在工作区右栏顶部,首页聊天根本没有,业主在首页让助手接工作区,
// 助手说"等你确认",屏幕上却找不到可以点的地方。现在每个聊天的输入卡上方都有,
// 数据来自共享的 chat/consentStore(三个聊天一份),由 ChatPage 渲染在输入卡里。
// 助手的工具会停下来等这张卡的结果(ds_tools_server.await_owner),所以点完助手直接接着干。
// 键盘照 ZCode:按 1 / 2 直接选,↑↓ 在两项之间移动,回车确认当前项。
//
// 助手想**扩大自己能看到的范围**(改工作区根 / 把项目指到某个文件夹)时,后端不落盘、
// 只排一条待确认;这张卡是业主点头的地方。没有待确认时整卡不渲染。
//
// 三条不许破的规矩(design 的三条硬性,改这个文件前先读):
//  ① **卡片内容由后端的 pending 记录渲染,不经助手转述。** 助手在聊天里说什么都不算
//     确认 —— 照搬 ds_organize 那句「聊天里说"确认"不算数」。所以这里只用
//     `fetchConsent()` 回来的 `params`,绝不接受聊天侧传进来的任何描述。
//  ② **提交时只带 pending_id**,不带"要执行什么"。执行参数由后端从落盘记录读
//     (design 装包前向兼容第 2 条:否则换外壳要重写,且开一个"确认后掉包"的洞)。
//  ③ **影响面那句话必须写在卡上。** 这是本单唯一"有意偏离现有原则"换来的东西 ——
//     仓里原则是"网页只批工作区内的事",而改根是最"外"的动作。拍板允许网页批,
//     代价就是这张卡得让业主看懂他在批什么。**别把它简化成「助手请求权限 [同意]」。**
//
// 这道闸挡不住"业主自己点了同意";它把"文档里藏一句话就能得手"降级成
// "得骗过业主眼皮底下的一张卡"。所以文案的清楚程度就是这道闸的强度。

type Props = {
  /** 待确认列表(来自 chat/consentStore;空 = 整卡不渲染)。 */
  pending: ConsentPending[];
  /** 这个聊天正在跑一轮 —— 此时助手多半正停在工具里等这张卡。 */
  waiting?: boolean;
  /** 点完之后回调(ChatPage 据 `res.waiter` 决定要不要在对话里替业主说一句)。 */
  onDecided?: (p: ConsentPending, approve: boolean, res: ConsentResolved) => void;
};

/** 后端 `resolve_pending` 能回的每个错误码 → 一句人话。
 *
 * 业主不写代码,屏幕上不该出现 `stale_pending` 这种东西。**新增错误码必须在这里
 * 补一句** —— `tests/test_consent_messages.mjs`(判据 O12)从 `ds_consent.py` 现取
 * 码表机械核对,漏一个就红,不靠谁记得回来看这段注释。
 */
const ERR_MSG: Record<string, string> = {
  already_resolved: "这一条已经处理过了(可能在另一个窗口点过)。",
  stale_pending: "这条请求排队之后,工作区被换过了 —— 卡片上写的文件夹名现在可能指向别的地方,所以没有执行。让助手重新提一次。",
  pending_not_found: "这一条已经不在了(可能刚被处理掉或清理掉)。",
  bad_pending: "这一条的内容读不出来,什么都没做。让助手重新提一次。",
  bad_pending_id: "这一条的编号不对,什么都没做。刷新页面后再试一次。",
  bad_approve: "请求格式不对,什么都没做。刷新页面后再试一次。",
  no_applier: "工作台这一侧没能执行它,什么都没做 —— 卡片还留着,可以再点一次。",
};

/** 把一条待确认翻译成人话:【它想干什么】+【同意之后会怎样】。
 *
 * 第二句是重点 —— 业主关心的不是"调用了哪个工具",是"我点了之后,它就能看到什么"。
 */
export function describe(p: ConsentPending): { title: string; impact: string } {
  const params = p.params || {};
  if (p.action === "set_workspace") {
    const root = String(params.root ?? "");
    return {
      title: `助手想把工作区根目录改成:${root}`,
      // 纯文本渲染,别在这里写 markdown 星号(会原样显示成 `**`)。
      impact: `同意之后,助手就能读取 ${root} 下所有项目的资料文档`
        + "(合同、报价、业主意见),内容会随对话上传到大模型。",
    };
  }
  if (p.action === "bind_project") {
    const project = String(params.project ?? "");
    const folder = String(params.folder ?? "");
    return {
      title: `助手想把项目「${project}」关联到文件夹「${folder}」`,
      // 第二句是四审提的:业主点完会看到项目列表少一行(两条重复条目合并了)。
      // 那不是安全后果,但不说他会困惑"我是不是批了别的事"。
      impact: `同意之后,助手就能读取那个文件夹里 01-资料 的文档,`
        + "内容会随对话上传到大模型;项目列表里那两条重复的条目也会合并成一条。",
    };
  }
  // 认不出的动作:**不猜**。宁可说不出所以然,也不能给一个可能是错的解释 ——
  // 业主是照着这句话点同意的。
  return {
    title: `助手请求一个本工作台还不认识的动作:${p.action}`,
    impact: "看不懂就先点「拒绝」,然后把这句话告诉开发者。",
  };
}

export default function ConsentCard({ pending, waiting = false, onDecided }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const optRefs = useRef<Record<string, (HTMLButtonElement | null)[]>>({});

  const decide = useCallback((p: ConsentPending, approve: boolean) => {
    setErr("");
    setBusy(p.pending_id);
    resolveConsent(p.pending_id, approve)
      .then((res) => onDecided?.(p, approve, res))
      .catch((e: Error) => {
        const code = e.message || "";
        // 兜底那一支是给 apply 阶段冒出来的业务错误码用的(比如批准时那个文件夹
        // 刚好被改名了)。它们不在 ERR_MSG 的管辖范围内,但也不能让界面白屏 ——
        // 留着码是为了业主截图给我看时还查得出来,前面那句话保证他知道"没改成"。
        setErr(ERR_MSG[code] || `这件事没能完成,工作区没有被改动(${code})。`);
      })
      // 无论如何重拉一次,别让界面停在旧状态
      .finally(() => {
        setBusy(null);
        refreshConsent();
      });
  }, [onDecided]);

  if (pending.length === 0) return null;

  // 键盘(照 ZCode PermissionDialog):焦点在某一条的选项上时,1=拒绝、2=同意,
  // ↑↓←→ 在两项间移动,回车/空格就是按钮本身的点击。**不自动抢焦点**:
  // 业主可能正在输入框里打下一句,弹卡时把焦点抢走,他下一下回车就成了替他做决定。
  const onKey = (p: ConsentPending) => (e: KeyboardEvent<HTMLDivElement>) => {
    if (busy === p.pending_id) return;
    if (e.key === "1" || e.key === "2") {
      e.preventDefault();
      decide(p, e.key === "2");
      return;
    }
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      e.preventDefault();
      const opts = optRefs.current[p.pending_id] || [];
      const at = opts.findIndex((b) => b === document.activeElement);
      const next = at < 0 ? 0 : (at + (e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 1) + 2) % 2;
      opts[next]?.focus();
    }
  };

  return (
    <div className="consent-card" data-ui="consent-card" role="group" aria-label="需要你同意">
      <div className="consent-head">
        <span className="t">
          需要你同意{pending.length > 1 ? `(${pending.length} 项)` : ""}
        </span>
        {waiting && <span className="consent-wait">助手在等你决定</span>}
      </div>
      {pending.map((p) => {
        const { title, impact } = describe(p);
        const refs = (optRefs.current[p.pending_id] ||= []);
        return (
          <div className="consent-item" key={p.pending_id} data-ui="consent-item"
               onKeyDown={onKey(p)}>
            <div className="consent-title">{title}</div>
            <div className="consent-impact">{impact}</div>
            <div className="consent-actions">
              {/* 按钮角色沿用仓里既定的那套(track opendesign-button-roles):
                  btn-primary / btn-secondary,别在这里发明第三种。
                  「拒绝」放主按钮位、排第 1 个是刻意的**不对称**(ZCode 是「允许」在前,
                  这里不照搬):这张卡是安全闸,拿不准时的正确动作是拒绝(拒了再让助手
                  重提一次,成本很低;误同意则是不可撤销地把资料面打开了)。
                  编号用 data-key + CSS 画出来,不进按钮文字(e2e 按文字认「拒绝」)。 */}
              <button
                ref={(b) => { refs[0] = b; }}
                className="btn-primary consent-opt"
                data-key="1"
                aria-keyshortcuts="1"
                disabled={busy === p.pending_id}
                onClick={() => decide(p, false)}
              >
                拒绝
              </button>
              <button
                ref={(b) => { refs[1] = b; }}
                className="btn-secondary consent-opt"
                data-key="2"
                aria-keyshortcuts="2"
                disabled={busy === p.pending_id}
                onClick={() => decide(p, true)}
              >
                同意
              </button>
            </div>
          </div>
        );
      })}
      {err && <div className="consent-err">{err}</div>}
      <div className="consent-hint">点选,或按 1 / 2</div>
    </div>
  );
}
