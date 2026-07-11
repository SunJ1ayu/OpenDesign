import { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar, { type SessionItem } from "./workspace/Sidebar";
import ChangesColumn from "./workspace/ChangesColumn";
import TodoPage from "./TodoPage";
import { ChatSession } from "./chat/connection";
import {
  fetchChanges,
  fetchProjects,
  fetchTodosOpenCount,
  type Change,
  type Project,
} from "./api";

// 主工作区外壳(P2 T2,handoff §Overall Layout):四列横向 flex ——
// 侧栏 240 / 变更记录 flex:1 / 图片+文件 290 / AI 聊天 340。
// hash 路由:#/ = 工作区(默认);todos / calendar / skills 保留占位页。
// 深色:定稿仅浅色,不再挂 .dark(设置弹层里标「即将支持」,design 风险项)。
// 伴随列/聊天列的真身在 T3 接入;此处先立骨架占位保证壳完整。

type Route = "workspace" | "todos" | "calendar" | "skills";

function fromHash(): Route {
  const h = window.location.hash.replace(/^#\//, "");
  if (h === "todos" || h === "calendar" || h === "skills") return h;
  return "workspace";
}

const SKILLS = [
  { name: "CAD 转 3D", desc: "户型 CAD 图纸转 3D 模型查看。", stage: "P2 接入" },
  { name: "PS 合成 PDF", desc: "批量图片排版合成一份 PDF 交付物。", stage: "规划中" },
] as const;

function SkillsPage() {
  return (
    <div className="page">
      <h2>技能</h2>
      <p className="muted">跑完就走的小工具都住这里;想到新的往里加卡片。</p>
      <div className="skill-grid">
        {SKILLS.map((s) => (
          <div className="skill-card" key={s.name}>
            <div className="nm">{s.name}</div>
            <div className="ds">{s.desc}</div>
            <span className="stg">{s.stage} · 未交付</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CalendarPage() {
  return (
    <div className="page placeholder">
      <h2>日历</h2>
      <p>项目排期、量房/交付节点与重要提醒,后续版本交付。</p>
    </div>
  );
}

// T2 骨架:伴随列与聊天列(T3 换成真身)
function AsideSkeleton() {
  return (
    <section className="aside">
      <div className="aside-head">
        <span className="t">图片</span>
        <span className="grow" />
      </div>
      <div className="aside-empty">图片区 T3 接入</div>
    </section>
  );
}

function ChatSkeleton() {
  return (
    <section className="chatcol">
      <div className="chatcol-head">
        <span className="t">项目助手</span>
        <span className="grow" />
      </div>
      <div className="chat-fill">
        <p>聊天列 T3 接入</p>
      </div>
    </section>
  );
}

export default function App() {
  const [route, setRoute] = useState<Route>(fromHash);
  const session = useMemo(() => new ChatSession(), []);

  // ---- 数据:项目 / 待办计数 / 服务信息 / 历史对话 ----
  const [projects, setProjects] = useState<Project[]>([]);
  const [projErr, setProjErr] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [changesErr, setChangesErr] = useState<string | null>(null);
  const [todosCount, setTodosCount] = useState<number | null>(null);
  const [health, setHealth] = useState<{ version: string; ds_root: string } | null>(null);
  const [sessions, setSessions] = useState<SessionItem[] | null>(null);

  // ---- 聊天联动:预填(标记完成/记一下/新建项目)与新对话(remount) ----
  const [prefill, setPrefill] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });
  const [chatEpoch, setChatEpoch] = useState(0);

  useEffect(() => {
    const onHash = () => setRoute(fromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    fetchProjects()
      .then((ps) => {
        setProjErr(null);
        setProjects(ps);
        setSelectedKey((cur) => {
          if (cur && ps.some((p) => p.key === cur)) return cur;
          // 默认选中:最近更新的未交付项目(设计师"手头项目"),否则第一个
          const active = ps.filter((p) => !p.delivered);
          const pick = (active.length ? active : ps)
            .slice()
            .sort((a, b) => (b.last_update ?? "").localeCompare(a.last_update ?? ""))[0];
          return pick ? pick.key : null;
        });
      })
      .catch((e: Error) => setProjErr(`读不到项目列表(${e.message})`));
    fetchTodosOpenCount().then(setTodosCount).catch(() => setTodosCount(null));
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setHealth({ version: d.version, ds_root: d.ds_root }))
      .catch(() => setHealth(null));
  }, []);

  // 选中项目变化 → 拉全量变更
  useEffect(() => {
    if (!selectedKey) {
      setChanges(null);
      return;
    }
    let stale = false;
    setChanges(null);
    setChangesErr(null);
    fetchChanges(selectedKey)
      .then((cs) => {
        if (!stale) setChanges(cs);
      })
      .catch((e: Error) => {
        if (!stale) setChangesErr(`读不到变更记录(${e.message})`);
      });
    return () => {
      stale = true;
    };
  }, [selectedKey]);

  // 历史对话:已登录才拉(经 ds_web 白名单代理,失败静默为 null)
  useEffect(() => {
    let stale = false;
    if (!session.hasPassword()) {
      setSessions(null);
      return;
    }
    session
      .apiFetch("/api/chat/sessions?limit=10&direction=latest")
      .then(async (r) => {
        if (r.status !== 200) throw new Error(String(r.status));
        const d = (await r.json()) as { sessions?: SessionItem[] };
        if (!stale) setSessions(d.sessions ?? []);
      })
      .catch(() => {
        if (!stale) setSessions(null);
      });
    return () => {
      stale = true;
    };
  }, [session, chatEpoch]);

  // ⌘N 新对话(handoff §Interactions)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        setChatEpoch((n) => n + 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const doPrefill = useCallback((text: string) => {
    setPrefill((p) => ({ text, nonce: p.nonce + 1 }));
  }, []);

  const onMarkDone = useCallback(
    (c: Change) => {
      // 只读安全基线:不加写 API;预填交 AI 走 ds_tools/ds-approve 既有闸(design 决策)
      const what = c.cnum !== null ? `C${c.cnum}` : `「${c.text.slice(0, 24)}」`;
      doPrefill(`把 ${what} 标记完成`);
    },
    [doPrefill],
  );

  const selected = projects.find((p) => p.key === selectedKey) ?? null;
  void prefill; // T3 起传入聊天列;先占位避免未用告警

  const sidebar = (
    <Sidebar
      projects={projects}
      selectedKey={selectedKey}
      onSelectProject={(k) => {
        setSelectedKey(k);
        window.location.hash = "#/";
      }}
      todosOpenCount={todosCount}
      sessions={sessions}
      onNewChat={() => {
        setChatEpoch((n) => n + 1);
        window.location.hash = "#/";
      }}
      onNewProject={() => {
        doPrefill("新建项目:");
        window.location.hash = "#/";
      }}
      health={health}
    />
  );

  if (route !== "workspace") {
    return (
      <div className="workspace">
        {sidebar}
        {route === "todos" && (
          <div className="page">
            <TodoPage />
          </div>
        )}
        {route === "calendar" && <CalendarPage />}
        {route === "skills" && <SkillsPage />}
      </div>
    );
  }

  return (
    <div className="workspace">
      {sidebar}
      {projErr ? (
        <section className="center">
          <div className="center-empty">
            <div className="error-note">{projErr}</div>
            <div className="muted">确认 ds-web 服务在跑,刷新重试。</div>
          </div>
        </section>
      ) : (
        <ChangesColumn
          project={selected}
          changes={changes}
          error={changesErr}
          onMarkDone={onMarkDone}
        />
      )}
      <AsideSkeleton />
      <ChatSkeleton />
    </div>
  );
}
