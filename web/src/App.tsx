import { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar, { type SessionItem } from "./workspace/Sidebar";
import ChangesColumn from "./workspace/ChangesColumn";
import CompanionColumn from "./workspace/CompanionColumn";
import ChatColumn from "./workspace/ChatColumn";
import ChatPage from "./chat/ChatPage";
import TodoPage from "./TodoPage";
import { ChatSession } from "./chat/connection";
import {
  fetchChanges,
  fetchProjects,
  fetchTodosOpenCount,
  type Change,
  type Project,
} from "./api";

// 外壳(P3 T1,handoff v2 导航模型):
//   hash 路由:#/ = home(3a 新对话,默认)| workspace(2a,点项目进入)
//   | todos | skills。calendar 删除(功能将来融进待办页)。项目不进 URL。
// keep-mounted(design.md 核心决策):3a HomeChat 与 2a ChatColumn 两个聊天
// 实例常驻,非当前路由用 CSS display:none 隐藏、不卸载(transcript/ws 自然
// 保留;协议每连接一会话,两实例各自独立)。「新对话」/⌘N = 回 3a 现状,
// 不重置对话(重置 = 亲手复刻"切页丢对话");会话管理是 T7。

type Route = "home" | "workspace" | "todos" | "skills";

function fromHash(): Route {
  const h = window.location.hash.replace(/^#\//, "");
  if (h === "workspace" || h === "todos" || h === "skills") return h;
  return "home";
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

  // ---- 聊天联动:两个常驻实例各有一份预填(3a 建议 chip/新建项目 → home;
  // 「✓ 标记完成」在 2a 中央列 → column),nonce 变化即覆盖 draft ----
  const [homePrefill, setHomePrefill] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });
  const [colPrefill, setColPrefill] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });
  const [sessionsEpoch, setSessionsEpoch] = useState(0); // 连接就绪后刷新历史对话

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
  }, [session, sessionsEpoch]);

  // ⌘N 新对话 = 回 3a 现状(不重置;UI 不显示角标,行为保留。handoff §Interactions)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        window.location.hash = "#/";
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const prefillHome = useCallback((text: string) => {
    setHomePrefill((p) => ({ text, nonce: p.nonce + 1 }));
  }, []);
  const prefillCol = useCallback((text: string) => {
    setColPrefill((p) => ({ text, nonce: p.nonce + 1 }));
  }, []);

  const onMarkDone = useCallback(
    (c: Change) => {
      // 只读安全基线:不加写 API;预填交 AI 走 ds_tools/ds-approve 既有闸(design 决策)
      const what = c.cnum !== null ? `C${c.cnum}` : `「${c.text.slice(0, 24)}」`;
      prefillCol(`把 ${what} 标记完成`);
    },
    [prefillCol],
  );

  const onConnected = useCallback(() => setSessionsEpoch((n) => n + 1), []);

  const selected = projects.find((p) => p.key === selectedKey) ?? null;

  const sidebar = (
    <Sidebar
      projects={projects}
      selectedKey={selectedKey}
      onSelectProject={(k) => {
        setSelectedKey(k);
        window.location.hash = "#/workspace";
      }}
      todosOpenCount={todosCount}
      sessions={sessions}
      onNewChat={() => {
        window.location.hash = "#/";
      }}
      onNewProject={() => {
        prefillHome("新建项目:");
        window.location.hash = "#/";
      }}
      health={health}
    />
  );

  return (
    <div className="workspace">
      {sidebar}

      {/* 3a 新对话页(常驻,非 home 路由时 CSS 隐藏不卸载) */}
      <section className={`home-pane${route === "home" ? "" : " route-hidden"}`}>
        <ChatPage
          variant="home"
          session={session}
          prefill={homePrefill}
          onConnected={onConnected}
        />
      </section>

      {/* 2a 主工作区三列(常驻,非 workspace 路由时 CSS 隐藏不卸载) */}
      <div className={`ws-pane${route === "workspace" ? "" : " route-hidden"}`}>
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
        <CompanionColumn projectKey={selectedKey} />
        <ChatColumn session={session} prefill={colPrefill} onConnected={onConnected} />
      </div>

      {/* 无状态占位页:每次进入重建,无所谓(design.md 取舍) */}
      {route === "todos" && (
        <div className="page">
          <TodoPage />
        </div>
      )}
      {route === "skills" && <SkillsPage />}
    </div>
  );
}
