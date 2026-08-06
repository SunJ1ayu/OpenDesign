import { useEffect, useRef, useState } from "react";
import type { IntakeData } from "../api";
import {
  amendIntake, approveIntake, createInbox, createInboxErrMsg, fetchIntake,
  openInbox, scanInbox,
} from "../api";
import { useInboxDrop } from "../inboxDrop";
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
  const [creating, setCreating] = useState(false); // 「帮我建收件箱」进行中
  // 建成后的确认(带绝对路径)。四审 subkimi 的一条:建完卡片会因为"空箱=隐身"整卡
  // 消失 —— 用户点了一下、东西没了,对一个不是程序员的人读起来像"坏了";而这一刻
  // 恰恰是最该把路径给他看一次的时候(他原话就是"收件箱在我电脑哪个文件夹")。
  const [created, setCreated] = useState("");
  const [openErr, setOpenErr] = useState("");

  // 常驻「打开」(-p2):点开资源管理器看那个文件夹。路径不由前端给(见 api.openInbox)。
  const doOpen = () => {
    setOpenErr("");
    openInbox().catch(() => setOpenErr("打开失败,可能是路径被改了或没有桌面环境"));
  };
  const inboxDrop = useInboxDrop({
    rejectMessage: "这个格式收不了。可以拖:图片、PDF、Word/Excel/PPT、"
      + "CAD(dwg/dxf)、SU、3ds Max、PSD;别的请点「打开」到文件夹里自己放。",
    successTail: " —— 点「扫描整理」归档",
    onUploaded: () => setLocalEpoch((e) => e + 1),
  });
  const inboxCardClass = `inbox-card${inboxDrop.dragOver ? " drag-over" : ""}`;
  const dropNote = (inboxDrop.dragOver || inboxDrop.upBusy || inboxDrop.upMsg) && (
    <div className="upload-note inbox-upload-note" data-ui="inbox-upload-note">
      {inboxDrop.dragOver ? "松手就存进收件箱" : inboxDrop.upBusy ? "上传中…" : inboxDrop.upMsg}
      {!inboxDrop.dragOver && !inboxDrop.upBusy && inboxDrop.upMsg && (
        <button className="link-act inline" onClick={() => inboxDrop.setUpMsg(null)}>
          知道了
        </button>
      )}
    </div>
  );
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

  // 建收件箱(针孔⑭):成功即刷新,卡片自然切到正常态(按钮随之消失)。
  const doCreateInbox = () => {
    setErr("");
    setCreating(true);
    createInbox()
      .then((r) => {
        setCreated(r.path);
        setLocalEpoch((e) => e + 1);
      })
      .catch((e: Error) => setErr(createInboxErrMsg(e.message || "unknown")))
      .finally(() => setCreating(false));
  };

  const state = intakeState(data);
  // 「收件箱夹根本不存在」不算"无事发生"(track opendesign-chat-image design D3):
  // 用户原话「每个用户不一定都有这个文件夹」+「收件箱是在我电脑哪个文件夹」——
  // 0.48.0 里这种情况整卡隐身、上传报一句"先建一个",活就被推回给一个不是程序员的人。
  // 这里给一条能点的出路,且**点之前就写清会建在哪**。
  // 只对 inbox_not_found 这一种原因出面:没接工作区/服务不可达是别的病,不在这治。
  if (state === "unconfigured") {
    const u = data as Extract<IntakeData, { configured: false }>;
    if (u.reason !== "inbox_not_found" || !u.wouldCreate) return null;
    return (
      <div className={inboxCardClass} data-ui="inbox-drop" {...inboxDrop.dropProps}>
        <div className="inbox-summary">
          <span className="t">收件箱</span>
        </div>
        {dropNote}
        <div className="inbox-expanded">
          <div className="inbox-hint" data-ui="inbox-missing">
            还没有收件箱文件夹。点一下我给你建在:<code>{u.wouldCreate}</code>
            <br />
            以后拖进来的图纸、文件、聊天里发的图都先落在这儿,再说「整理收件箱」归档。
          </div>
          {err && <div className="aside-empty warn">{err}</div>}
          <div className="plan-acts">
            <button
              className="btn-primary"
              data-ui="inbox-create"
              disabled={creating}
              onClick={doCreateInbox}
              title="在工作区根目录下建一个收件箱文件夹"
            >
              {creating ? "建立中…" : "帮我建收件箱"}
            </button>
          </div>
        </div>
      </div>
    );
  }
  // 其余"无事发生"(拉取中/空箱)照旧整卡隐身,伴随列寸土寸金 ——
  // 唯一例外:刚刚亲手建好收件箱的那一次,留一行确认告诉他建在哪了。
  if (state === "empty" && created) {
    return (
      <div className={inboxCardClass} data-ui="inbox-drop" {...inboxDrop.dropProps}>
        <div className="inbox-summary">
          <span className="t">收件箱</span>
        </div>
        {dropNote}
        <div className="inbox-expanded">
          <div className="inbox-hint" data-ui="inbox-created">
            已建好:<code>{created}</code>
            <br />
            以后拖进来的图纸、文件、聊天里发的图都先落这儿,再说「整理收件箱」归档。
          </div>
        </div>
      </div>
    );
  }
  if (state === "empty") {
    // -p2:空箱不再整卡隐身 —— 用户要的是**常驻**入口("这个常驻的打开收件箱")。
    // 一行,和左列 .aside-head 同款,不占地方。
    const dd = data as Extract<IntakeData, { configured: true }>;
    return (
      <div className={inboxCardClass} data-ui="inbox-drop" {...inboxDrop.dropProps}>
        <div className="inbox-summary" data-ui="inbox-summary">
          <span className="t">收件箱</span>
          <button className="btn-secondary" data-ui="inbox-open" title={dd.path || ""}
                  onClick={doOpen}>
            打开
          </button>
          <span className="grow" />
          <span className="inbox-quiet">空的,可拖图纸/PDF/图片进来</span>
        </div>
        {dropNote}
        {openErr && <div className="aside-empty warn">{openErr}</div>}
      </div>
    );
  }
  if (state === "loading") {
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
    <div className={inboxCardClass} data-ui="inbox-drop" {...inboxDrop.dropProps}>
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
        {/* 打开收件箱和左列「打开文件夹」同属资源管理器动作,统一用 .btn-secondary。 */}
        <button
          className="btn-secondary"
          data-ui="inbox-open"
          title="在资源管理器里打开收件箱"
          onClick={(e) => {
            e.stopPropagation();
            doOpen();
          }}
        >
          打开
        </button>
        <span className="grow" />
        <button
          className="btn-secondary"
          disabled={scanning}
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(true); // 收起态点扫描:结果(方案/提示)都在折叠区,先展开再扫
            doScan();
          }}
          title="自动认领确定性建议(扩展名/项目名唯一命中),歧义留人工"
        >
          {scanning ? "扫描中…" : "扫描整理"}
        </button>
        <span className="chev">{expanded ? "▴" : "▾"}</span>
      </div>
      {dropNote}

      {expanded && (
        <div className="inbox-expanded" data-ui="inbox-expanded">
          {/* 它在硬盘哪儿 —— 用户问过「收件箱是在我电脑哪个文件夹」,答案就该写在这。 */}
          {d.path && (
            <div className="inbox-where" data-ui="inbox-where" title={d.path}>
              <code>{d.path}</code>
            </div>
          )}
          {openErr && <div className="aside-empty warn">{openErr}</div>}
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
                  className="btn-primary"
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
