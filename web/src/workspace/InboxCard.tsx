import { useEffect, useRef, useState } from "react";
import type { IntakeData } from "../api";
import { amendIntake, approveIntake, fetchIntake, scanInbox } from "../api";
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
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState(""); // 扫描后的轻量提示(staged/skipped)
  // 修改单 D1:默认收成一行摘要,点行展开明细(寸土寸金,伴随列减负)。
  const [expanded, setExpanded] = useState(false);
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

  // 单条「跳过」(track opendesign-frontend-p1 design §②):与「确认执行」共用
  // busy 锁(键=`${planId}#skip#${i}`),防两键并发出两个互相打架的请求。
  const doSkip = (planId: string, i: number) => {
    setErr("");
    setBusy(`${planId}#skip#${i}`);
    amendIntake(planId, [i])
      .then(() => setLocalEpoch((e) => e + 1))
      .catch((e: Error) => setErr(e.message || "跳过失败"))
      .finally(() => setBusy(null));
  };

  const doScan = () => {
    setScanMsg("");
    setScanning(true);
    scanInbox()
      .then((r) => {
        if (r.staged > 0) {
          setLocalEpoch((e) => e + 1); // 新暂存的 plan 出现在待确认区
          setScanMsg(
            r.skipped.length > 0
              ? `已暂存 ${r.staged} 项,${r.skipped.length} 个需手动`
              : `已暂存 ${r.staged} 项`,
          );
        } else {
          setScanMsg("没有可自动认领的文件");
        }
      })
      .catch((e: Error) => setScanMsg(`扫描失败:${e.message || "未知错误"}`))
      .finally(() => setScanning(false));
  };

  return (
    <div className="inbox-card">
      <div
        className="inbox-summary"
        data-ui="inbox-summary"
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
      >
        <span className="t">收件箱 {d.entries.length}</span>
        <span className="grow" />
        <button
          className="btn-secondary sm"
          disabled={scanning}
          onClick={(e) => {
            e.stopPropagation();
            doScan();
          }}
          title="自动认领确定性建议(扩展名/项目名唯一命中),歧义留人工"
        >
          {scanning ? "扫描中…" : "扫描整理"}
        </button>
        <span className="chev">{expanded ? "▴" : "▾"}</span>
      </div>

      {expanded && (
        <div className="inbox-expanded" data-ui="inbox-expanded">
          {scanMsg && <div className="inbox-hint scan-msg">{scanMsg}</div>}

          {plans.map((p) => (
            <div className="inbox-plan" key={p.planId}>
              <div className="plan-title">待确认的整理方案({p.count} 项)</div>
              {p.rows.map((r, i) => (
                <div className="plan-row" key={`${p.planId}/${i}`}>
                  <span className="src" title={r.src}>{r.src}</span>
                  <span className="arrow">→</span>
                  <span className="dst" title={r.dstDir}>{r.dstDir}</span>
                  <button
                    className="skip-btn"
                    disabled={busy !== null}
                    onClick={() => doSkip(p.planId, i)}
                    title="跳过这一条,其余重新暂存"
                  >
                    跳过
                  </button>
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
          {/* 不断言"文件未动":apply_failed 属部分执行场景,已执行部分在审计日志 */}
          {err && <div className="aside-empty warn">执行失败:{err}(详见对话或审计日志)</div>}

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
              {d.truncated && (
                <div className="inbox-row more">收件箱文件过多,仅统计前 500 个</div>
              )}
              <div className="inbox-hint">
                在对话里说「整理收件箱」,确认方案后一键归位。
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
