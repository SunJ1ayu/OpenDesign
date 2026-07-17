import { useEffect, useRef, useState } from "react";
import type { IntakeData } from "../api";
import { approveIntake, fetchIntake } from "../api";
import { entrySuggestion, intakeState, planPreview } from "./intake";

// 收件箱卡片(track opendesign-intake,design D1/D2):工作区级,不随选中项目变。
// 只做两件事:①展示收件箱里待认领的文件+确定性建议(认领本身走聊天,agent 暂存);
// ②展示待确认 plan 的 src→dst 预览,「确认执行」= 人工批准本体(针孔④)。
// 没事(空箱且无待确认)时整卡不渲染,伴随列寸土寸金。

type Props = {
  /** 每轮聊天回复后 bump(同 cockpit M5):agent 刚 stage 的 plan 即刻上屏。 */
  dataEpoch: number;
  /** 路由门:仅工作区路由可见时拉数据。 */
  active: boolean;
};

export default function InboxCard({ dataEpoch, active }: Props) {
  const [data, setData] = useState<IntakeData | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // 执行中的 plan_id
  const [err, setErr] = useState("");
  const [localEpoch, setLocalEpoch] = useState(0); // 确认成功后自刷新
  const fetched = useRef<string | null>(null);

  useEffect(() => {
    if (!active) return;
    const stamp = `${dataEpoch}/${localEpoch}`;
    if (fetched.current === stamp) return;
    fetched.current = stamp;
    let stale = false;
    fetchIntake()
      .then((d) => {
        if (!stale) setData(d);
      })
      .catch(() => {
        if (!stale) {
          setData({ configured: false, reason: "unreachable",
                    entries: [], pending: [] });
        }
      });
    return () => {
      stale = true;
    };
  }, [dataEpoch, localEpoch, active]);

  const state = intakeState(data);
  // 没配置/空箱 = 无事发生,整卡隐身(收件箱有东西才冒出来)
  if (state === "loading" || state === "unconfigured" || state === "empty") {
    return null;
  }
  const d = data as Extract<IntakeData, { configured: true }>;
  const plans = planPreview(d.pending);

  const doApprove = (planId: string) => {
    setErr("");
    setBusy(planId);
    approveIntake(planId)
      .then(() => setLocalEpoch((e) => e + 1))
      .catch((e: Error) => setErr(e.message || "执行失败"))
      .finally(() => setBusy(null));
  };

  return (
    <div className="inbox-card">
      <div className="aside-head">
        <span className="t">收件箱</span>
        <span className="inbox-count">{d.entries.length}</span>
        <span className="grow" />
      </div>

      {plans.map((p) => (
        <div className="inbox-plan" key={p.planId}>
          <div className="plan-title">待确认的整理方案({p.count} 项)</div>
          {p.rows.map((r, i) => (
            <div className="plan-row" key={`${p.planId}/${i}`}>
              <span className="src" title={r.src}>{r.src}</span>
              <span className="arrow">→</span>
              <span className="dst" title={r.dstDir}>{r.dstDir}</span>
            </div>
          ))}
          <div className="plan-acts">
            <button
              className="chat-btn primary"
              disabled={busy !== null}
              onClick={() => doApprove(p.planId)}
              title="确认后文件才会真正移动"
            >
              {busy === p.planId ? "执行中…" : "确认执行"}
            </button>
            <span className="plan-hint">不对?在对话里说怎么改,助手会重新暂存。</span>
          </div>
        </div>
      ))}
      {err && <div className="aside-empty warn">执行失败:{err}(文件未动,详见对话)</div>}

      {d.entries.length > 0 && (
        <div className="inbox-list">
          {d.entries.slice(0, 6).map((e) => (
            <div className="inbox-row" key={e.name}>
              <span className="n" title={e.name}>{e.name}</span>
              <span className="grow" />
              <span className="sug">{entrySuggestion(e)}</span>
            </div>
          ))}
          {d.entries.length > 6 && (
            <div className="inbox-row more">…还有 {d.entries.length - 6} 个</div>
          )}
          <div className="inbox-hint">
            在对话里说「整理收件箱」,确认方案后一键归位。
          </div>
        </div>
      )}
    </div>
  );
}
