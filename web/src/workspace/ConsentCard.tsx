import { useCallback, useEffect, useState } from "react";
import type { ConsentPending } from "../api";
import { fetchConsent, resolveConsent } from "../api";

// 业主同意卡(track opendesign-owner-consent)。
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
  /** 每轮聊天回复后 bump:助手刚排的队即刻上屏(同 InboxCard 的节拍)。 */
  dataEpoch: number;
  /** 路由门:仅工作区路由可见时拉数据。 */
  active: boolean;
};

/** 把一条待确认翻译成人话:【它想干什么】+【同意之后会怎样】。
 *
 * 第二句是重点 —— 业主关心的不是"调用了哪个工具",是"我点了之后,它就能看到什么"。
 */
function describe(p: ConsentPending): { title: string; impact: string } {
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
      impact: `同意之后,助手就能读取那个文件夹里 01-资料 的文档,`
        + "内容会随对话上传到大模型。",
    };
  }
  // 认不出的动作:**不猜**。宁可说不出所以然,也不能给一个可能是错的解释 ——
  // 业主是照着这句话点同意的。
  return {
    title: `助手请求一个本工作台还不认识的动作:${p.action}`,
    impact: "看不懂就先点「拒绝」,然后把这句话告诉开发者。",
  };
}

export default function ConsentCard({ dataEpoch, active }: Props) {
  const [pending, setPending] = useState<ConsentPending[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [localEpoch, setLocalEpoch] = useState(0);

  useEffect(() => {
    if (!active) return;
    let stale = false;
    fetchConsent()
      .then((s) => {
        if (!stale) setPending(s.pending || []);
      })
      .catch(() => {
        // 拉不到就当没有待确认:这张卡是**加法**,它自己坏掉不该把工作台带塌。
        // (真正的安全保证在后端 —— 拉不到卡不等于闸失效,那边照样不落盘。)
        if (!stale) setPending([]);
      });
    return () => {
      stale = true;
    };
  }, [dataEpoch, localEpoch, active]);

  const decide = useCallback((pendingId: string, approve: boolean) => {
    setErr("");
    setBusy(pendingId);
    resolveConsent(pendingId, approve)
      .then(() => setLocalEpoch((e) => e + 1))
      .catch((e: Error) => {
        const code = e.message || "";
        setErr(code === "already_resolved"
          ? "这一条已经处理过了(可能在另一个窗口点过)。"
          : `没能提交:${code}`);
        setLocalEpoch((e2) => e2 + 1); // 无论如何重拉一次,别让界面停在旧状态
      })
      .finally(() => setBusy(null));
  }, []);

  if (!active || pending.length === 0) return null;

  return (
    <div className="consent-card" data-ui="consent-card">
      <div className="consent-head">
        <span className="t">需要你确认</span>
      </div>
      {pending.map((p) => {
        const { title, impact } = describe(p);
        return (
          <div className="consent-item" key={p.pending_id} data-ui="consent-item">
            <div className="consent-title">{title}</div>
            <div className="consent-impact">{impact}</div>
            <div className="consent-actions">
              {/* 按钮角色沿用仓里既定的那套(track opendesign-button-roles):
                  btn-primary / btn-secondary,别在这里发明第三种。
                  「拒绝」放主按钮位是刻意的**不对称**:这张卡是安全闸,
                  拿不准时的正确动作是拒绝(拒了再让助手重提一次,成本很低;
                  误同意则是不可撤销地把资料面打开了)。 */}
              <button
                className="btn-primary"
                disabled={busy === p.pending_id}
                onClick={() => decide(p.pending_id, false)}
              >
                拒绝
              </button>
              <button
                className="btn-secondary"
                disabled={busy === p.pending_id}
                onClick={() => decide(p.pending_id, true)}
              >
                同意
              </button>
            </div>
          </div>
        );
      })}
      {err && <div className="consent-err">{err}</div>}
    </div>
  );
}
