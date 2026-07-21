import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Sidebar, { type SessionItem } from "./workspace/Sidebar";
import ChangesColumn from "./workspace/ChangesColumn";
import CompanionColumn from "./workspace/CompanionColumn";
import ChatColumn from "./workspace/ChatColumn";
import ChatPage from "./chat/ChatPage";
import TodoPage from "./TodoPage";
import SkillsPage from "./SkillsPage";
import GalleryPage from "./GalleryPage";
import SearchPanel from "./SearchPanel";
import { ChatSession } from "./chat/connection";
import {
  loadThreadMap,
  projectPrefix,
  sessionLabels,
  threadFor,
  THREADS_STORAGE_KEY,
  withThread,
  withoutThread,
  type ThreadMap,
} from "./chat/projectThread";
import {
  deleteChatSession,
  fetchChanges,
  fetchProjectsData,
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

type Route = "home" | "workspace" | "todos" | "skills" | "gallery";

function fromHash(): Route {
  const h = window.location.hash.replace(/^#\//, "");
  if (h === "workspace" || h === "todos" || h === "skills" || h === "gallery") return h;
  return "home";
}

export default function App() {
  const [route, setRoute] = useState<Route>(fromHash);
  const session = useMemo(() => new ChatSession(), []);

  // ---- 数据:项目 / 待办计数 / 服务信息 / 历史对话 ----
  const [projects, setProjects] = useState<Project[]>([]);
  // 阶段词表(track opendesign-stage-history §7):随项目列表一起下发,单一真相源
  // = 后端 ds_tools.PROJECT_STAGES;ChangesColumn 的 stage-chip 下拉直接用它,不硬编码副本。
  const [stages, setStages] = useState<string[]>([]);
  const [projErr, setProjErr] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [changesErr, setChangesErr] = useState<string | null>(null);
  const [todosCount, setTodosCount] = useState<number | null>(null);
  const [health, setHealth] = useState<
    { version: string; ds_root: string; model: string | null } | null
  >(null);
  const [sessions, setSessions] = useState<SessionItem[] | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  // 搜索回车直达:中央列滚动定位+闪烁(nonce 驱动,cnum=null 只跳项目)
  const [colHighlight, setColHighlight] = useState<{ cnum: number | null; nonce: number }>({
    cnum: null,
    nonce: 0,
  });

  // ---- 聊天联动:3a 建议 chip/新建项目 → home 实例预填,nonce 变化即覆盖 draft
  // (中央列曾有 colPrefill,唯一调用者「接入工作区」改走 dispatch 后删净) ----
  const [homePrefill, setHomePrefill] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });
  // 中央列 ChatColumn 的程序化发送(connect-ux)。用途:「接入工作区」表单确认后
  // 组装完整消息直接发进同屏工作区聊天(而非主页,防上下文跳脱),人留在原地;
  // 未连接/busy 时 ChatPage 自己降级为预填,动作不丢。
  const [colDispatch, setColDispatch] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });
  const dispatchCol = useCallback((text: string) => {
    setColDispatch((p) => ({ text, nonce: p.nonce + 1 }));
  }, []);
  const [sessionsEpoch, setSessionsEpoch] = useState(0); // 连接就绪/每轮回复后刷新历史对话
  // M5(07-13 盲评):每轮回复收尾后,AI 可能刚记了变更/改了状态——变更列、待办角标、
  // 项目列表都要跟着刷,否则聊完仍要 F5(p6 只修了历史对话侧栏这一半)。
  const [dataEpoch, setDataEpoch] = useState(0);
  // p6 续聊目标:点历史行 → 首页聊天实例 attach 挂回该会话(null = 新对话)
  const [resumeTarget, setResumeTarget] = useState<{
    sessionKey: string;
    chatId: string;
    nonce: number;
  } | null>(null);

  // ---- 项目级对话(project-thread):每项目一条工作对话 ----
  // 映射 项目→chat_id 存 localStorage(本机;丢=重开新对话,PKB 零损失)。
  const [projThreads, setProjThreads] = useState<ThreadMap>(() =>
    loadThreadMap(localStorage.getItem(THREADS_STORAGE_KEY)),
  );
  useEffect(() => {
    try {
      localStorage.setItem(THREADS_STORAGE_KEY, JSON.stringify(projThreads));
    } catch {
      /* 隐私模式等存不进:映射退化为会话级,不炸 */
    }
  }, [projThreads]);
  // 工作区聊天列的连接上下文:切项目才重派生(映射更新不触发重连)。
  // resume.chatId 空串 = 强制新会话(见 ChatPage resume 注释)。project 字段
  // 记"这条连接是替哪个项目发起的"——记账/自愈回调按它闭包绑定,连接建立中
  // 用户切走项目也不会记错账(ChatPage effect 捕获的是发起时的回调)。
  const [colChat, setColChat] = useState<{
    project: string;
    resume: { sessionKey: string; chatId: string; nonce: number };
  } | null>(null);
  const selKeyRef = useRef<string | null>(null); // 自愈判断"当前还在这个项目吗"用
  useEffect(() => {
    selKeyRef.current = selectedKey;
    if (!selectedKey) return; // 无选中项目:保持现状(初始 null=旧行为)
    const chatId = threadFor(projThreads, selectedKey);
    setColChat((prev) => ({
      project: selectedKey,
      resume: {
        sessionKey: chatId ? `websocket:${chatId}` : "",
        chatId: chatId ?? "",
        nonce: (prev?.resume.nonce ?? 0) + 1,
      },
    }));
    // projThreads 故意不入依赖:记账更新不该触发重连,只有切项目才重派生
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey]);
  // 记账:绑定发起时的项目(colChat 闭包)。连上即记(eager)——虚会话 attach
  // 失败有自愈兜底;晚到的回调也记在正确的项目名下。
  const onColChatId = useCallback(
    (chatId: string) => {
      const proj = colChat?.project;
      if (!proj) return;
      setProjThreads((m) => (m[proj] === chatId ? m : withThread(m, proj, chatId)));
    },
    [colChat],
  );
  // 映射指向的会话已删/打不开 → 清该项目映射;仍停在该项目才重连自愈
  // (已切走就不打扰当前连接,下次回来自然走"无映射=新会话")
  const onColAttachFailed = useCallback(() => {
    const proj = colChat?.project;
    if (!proj) return;
    setProjThreads((m) => withoutThread(m, proj));
    if (selKeyRef.current === proj) {
      setColChat((prev) =>
        prev
          ? { project: proj, resume: { sessionKey: "", chatId: "", nonce: prev.resume.nonce + 1 } }
          : prev,
      );
    }
  }, [colChat]);
  // 聊天列「+ 新对话」:断开当前项目映射重开一条;旧会话退回全局历史(可点回续聊)
  const newProjectChat = useCallback(() => {
    const proj = selectedKey;
    if (!proj) return;
    setProjThreads((m) => withoutThread(m, proj));
    setColChat((prev) => ({
      project: proj,
      resume: { sessionKey: "", chatId: "", nonce: (prev?.resume.nonce ?? 0) + 1 },
    }));
  }, [selectedKey]);

  useEffect(() => {
    const onHash = () => setRoute(fromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // 项目列表 + 待办角标:挂载即拉,dataEpoch 变(每轮回复后)重拉——刷新变更来源
  useEffect(() => {
    fetchProjectsData()
      .then(({ projects: ps, stages: st }) => {
        setProjErr(null);
        setProjects(ps);
        setStages(st);
        setSelectedKey((cur) => {
          if (cur && ps.some((p) => p.key === cur)) return cur;
          // 默认选中:最近更新的未交付已建档项目(设计师"手头项目");
          // 未建档文件夹(p7)不抢默认位,除非列表里只有它们
          const pkb = ps.filter((p) => !p.unregistered);
          const active = pkb.filter((p) => !p.delivered);
          const pick = (active.length ? active : pkb.length ? pkb : ps)
            .slice()
            .sort((a, b) => (b.last_update ?? "").localeCompare(a.last_update ?? ""))[0];
          return pick ? pick.key : null;
        });
      })
      .catch((e: Error) => setProjErr(`读不到项目列表(${e.message})`));
    fetchTodosOpenCount().then(setTodosCount).catch(() => setTodosCount(null));
  }, [dataEpoch]);

  // 服务信息:挂载一次(版本/model/ds_root 不随聊天变)
  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setHealth({ version: d.version, ds_root: d.ds_root, model: d.model ?? null }))
      .catch(() => setHealth(null));
  }, []);

  // 选中项目变化 → 拉全量变更(未建档项目没有档案,不请求,由中央列给引导)
  useEffect(() => {
    if (!selectedKey) {
      setChanges(null);
      return;
    }
    if (projects.find((p) => p.key === selectedKey)?.unregistered) {
      setChanges([]);
      setChangesErr(null);
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
  }, [selectedKey, projects]);

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

  // ⌘N 新对话 = 回 3a 现状;⌘K 搜索面板(UI 不显示角标,行为保留。handoff §Interactions)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        setResumeTarget(null); // 与「新对话」同语义(见 newChat 注释)
        window.location.hash = "#/";
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const prefillHome = useCallback((text: string) => {
    setHomePrefill((p) => ({ text, nonce: p.nonce + 1 }));
  }, []);

  const onConnected = useCallback(() => setSessionsEpoch((n) => n + 1), []);
  // p6:每轮回复收尾刷新历史对话侧栏(新会话首轮后即出现,免 F5);
  // M5:同时 bump dataEpoch → 项目列表+待办角标重拉,变更列经 projects 刷新链跟着重拉。
  const onTurnEnd = useCallback(() => {
    setSessionsEpoch((n) => n + 1);
    setDataEpoch((n) => n + 1);
  }, []);

  // p6:点历史对话行 → 回首页并 attach 续聊(会话 key = websocket:<chat_id>)
  const openSession = useCallback((s: { key: string }) => {
    if (!s.key.startsWith("websocket:")) return;
    const chatId = s.key.slice("websocket:".length);
    setResumeTarget((prev) => ({
      sessionKey: s.key,
      chatId,
      nonce: (prev?.nonce ?? 0) + 1,
    }));
    window.location.hash = "#/";
  }, []);

  // p7:删除历史对话。确认闸在这层(window.confirm);删的是当前续聊目标时清
  // resume(已渲染 transcript 不清,与 p3「新对话不重置」同语义,accepted deviation)
  const deleteSession = useCallback(
    async (s: SessionItem) => {
      const label = s.title || s.preview || "未命名对话";
      if (!window.confirm(`删除对话「${label}」?删除后不可恢复。`)) return;
      try {
        const res = await deleteChatSession(session, s.key);
        if (res.deleted) {
          // 清掉指向该会话的项目映射(防项目列 attach 已删会话;attach 失败
          // 本就有自愈,这里是主路径直接清干净)
          setProjThreads((m) => {
            const hits = Object.entries(m).filter(([, cid]) => `websocket:${cid}` === s.key);
            return hits.reduce((acc, [p]) => withoutThread(acc, p), m);
          });
        }
        if (!res.deleted) {
          window.alert(
            res.blocked_by_automations
              ? "该对话绑定了定时任务,暂不能从这里删除。"
              : "删除失败,稍后再试。",
          );
          return;
        }
        setResumeTarget((prev) => (prev?.sessionKey === s.key ? null : prev));
        setSessionsEpoch((n) => n + 1);
      } catch {
        window.alert("删除失败:服务不可用或登录已过期。");
      }
    },
    [session],
  );

  // 新对话:回 3a。p3 的「不重置对话」只针对误触丢对话——现在历史对话可点回
  // (本 track),从续聊态开新对话不再是丢失,所以 resume 态下清目标重连拿新
  // chat_id;非 resume 态维持 p3 现状(setState(null→null) React bail-out,零重连)。
  const newChat = useCallback(() => {
    setResumeTarget(null);
    window.location.hash = "#/";
  }, []);

  // 进某个项目的工作区(侧栏点击 / 待办「去项目」/ 搜索直达 共用)
  const goProject = useCallback((key: string) => {
    setSelectedKey(key);
    window.location.hash = "#/workspace";
  }, []);

  const openChangeFromSearch = useCallback(
    (project: string, cnum: number | null) => {
      goProject(project);
      setColHighlight((h) => ({ cnum, nonce: h.nonce + 1 }));
    },
    [goProject],
  );

  // 技能卡 → 3a 新对话预填话术
  const useSkill = useCallback(
    (text: string) => {
      prefillHome(text);
      window.location.hash = "#/";
    },
    [prefillHome],
  );

  const selected = projects.find((p) => p.key === selectedKey) ?? null;
  // 历史行项目小标:命中项目映射的会话标上项目名
  const sessionTags = useMemo(() => sessionLabels(projThreads, projects), [projThreads, projects]);

  const sidebar = (
    <Sidebar
      route={route}
      projects={projects}
      selectedKey={selectedKey}
      onSelectProject={goProject}
      onSearch={() => setSearchOpen(true)}
      todosOpenCount={todosCount}
      sessions={sessions}
      sessionTags={sessionTags}
      onOpenSession={openSession}
      onDeleteSession={deleteSession}
      onNewChat={newChat}
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
          onTurnEnd={onTurnEnd}
          resume={resumeTarget}
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
            stages={stages}
            onEdited={() => setDataEpoch((n) => n + 1)}
            onCreated={(key) => {
              setSelectedKey(key);
              setDataEpoch((n) => n + 1);
            }}
            highlight={colHighlight}
          />
        )}
        <CompanionColumn
          projectKey={selectedKey}
          project={selected}
          dataEpoch={dataEpoch}
          active={route === "workspace"}
          onOpenGallery={() => {
            window.location.hash = "#/gallery";
          }}
          onConnectWorkspace={(path) =>
            dispatchCol(`把我的项目文件夹接进来,路径是:${path}`)
          }
          folders={projects.filter((p) => p.unregistered).map((p) => p.key)}
          onBound={() => setDataEpoch((n) => n + 1)}
          onPrefillRegRef={() => dispatchCol("我发一张图,帮我登记参考图")}
        />
        <ChatColumn
          session={session}
          dispatch={colDispatch}
          onConnected={onConnected}
          onTurnEnd={onTurnEnd}
          resume={colChat?.resume ?? null}
          onChatId={onColChatId}
          onAttachFailed={onColAttachFailed}
          firstSendPrefix={selected ? projectPrefix(selected.name || selected.key) : undefined}
          onNewChat={newProjectChat}
        />
      </div>

      {/* 无状态页:每次进入重建,无所谓(design.md 取舍) */}
      {route === "todos" && (
        <TodoPage
          projects={projects}
          onGoProject={goProject}
          onEdited={() => setDataEpoch((n) => n + 1)}
        />
      )}
      {route === "skills" && <SkillsPage onUseSkill={useSkill} />}
      {route === "gallery" && <GalleryPage project={selected} />}

      {/* 5a 搜索命令面板(⌘K 浮层,盖在当前页上) */}
      <SearchPanel
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onOpenChange={openChangeFromSearch}
        onOpenProject={goProject}
      />
    </div>
  );
}
