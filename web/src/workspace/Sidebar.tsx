import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { hasDesktopUpdateBadge, RESTART_HINT, showRestart } from "../desktopUpdate";
import type { DesktopUpdateState } from "../desktopShell";
import type { Project } from "../api";
import { relTime } from "../api";
import { displayProjectName } from "./projectName";
import GroupToggle from "../GroupToggle";
import { SideIcon } from "./icons";
import {
  groupProjectsByStage, isStageGroupOpen, loadStagePrefs, revealStage,
  SIDE_STAGE_STORAGE_KEY, type StageGroup, type StagePrefs,
} from "./projectGroups";
import { byRecent, cleanRename, displayTitle, firstTag, projectView, timeSections } from "./sidebarModel";

// 左侧栏 v2(P3 T3,handoff §1,240px):品牌 / 全局操作组(新对话/搜索/
// 待办事项/技能)/ 历史对话 / 项目 / 设置入口(09-24 起开设置整页)。图标 09-23 由 Unicode 占位换成
// ZCode 同款 lucide 线条图标(./icons.tsx;历史行不再带图标)。v2 要点:日历行删除(功能将来融进待办页)、技能上移进
// 全局操作组、快捷键角标(⌘N/⌘K)从 UI 移除(keydown 行为在 App 保留)、
// 所有行共用 16px 图标列居中对齐;全局操作组按路由呈当前态(新对话=home、
// 待办事项=todos、技能=skills;搜索是弹层无路由不设),
// 项目行的白底卡片当前态只在 workspace 路由呈现(t3 画板:3a 下项目行均普通态,
// 仅选中项目圆点保持赤陶)。
// 09-25 历史对话照 ZCode 改(track opendesign-sidebar-history,业主「方案一和方案二一起做」):
// 置顶区 +「按时间 | 按项目」切换(记住上次选的);按时间 = 今天 / 昨天 / 更早 + 显示更多;
// 按项目 = 项目栏每个项目右边的数字展开它的对话 + 最下「其他对话」;每行「⋯」置顶 / 改名 / 删除。
// 中间(历史 + 项目 + 其他)一整块滚动,「显示更多」不会把项目栏挤出去(4c C5)。

/** 两种视图记在本机(不是业主数据,丢了回默认「按时间」)。 */
export const SIDE_VIEW_STORAGE_KEY = "odw.sideView";
type SideView = "time" | "project";
const TIME_FIRST = 10;   // 按时间先显示几条
const LIST_FIRST = 5;    // 项目 / 其他对话展开后先显示几条
const MORE_STEP = 20;    // 每点一次「显示更多」多几条

export type SessionItem = { key: string; title?: string; preview?: string; updated_at?: string };

type Props = {
  /** "settings" 时侧栏不渲染(设置页自带栏目),这里只为类型完整。 */
  route: "home" | "workspace" | "todos" | "skills" | "gallery" | "settings";
  projects: Project[];
  /** 阶段词表(/api/projects 下发,单一真相源 = 后端 PROJECT_STAGES):项目分堆的排序依据 */
  stages: string[];
  selectedKey: string | null;
  onSelectProject: (key: string) => void;
  todosOpenCount: number | null;
  sessions: SessionItem[] | null; // null = 未连接/不可用(隐藏区块内容)
  /** -p2:被"猜"成结构目录、因此没进列表的文件夹名(显式声明的不报) */
  excludedStructural?: string[];
  /** 每段对话碰过的项目 key(项目对话在前;App 由 sidebarModel.sessionProjects 算好) */
  sessionProjects: Record<string, string[]>;
  /** 项目对话(project-thread 映射)的会话 key:按项目视图里排在它自己项目的最前 */
  threadKeys: ReadonlySet<string>;
  pinnedKeys: string[];
  titleOverrides: Record<string, string>;
  onOpenSession: (s: SessionItem) => void; // p6:点历史行 → 首页 attach 续聊
  onDeleteSession: (s: SessionItem) => void; // ⋯ → 删除,确认在 App 层
  onPinSession: (s: SessionItem, pinned: boolean) => void;
  /** 只在名字真变了时调;空名字在这层就当取消,不会传进来 */
  onRenameSession: (s: SessionItem, title: string) => void;
  onNewChat: () => void;
  onNewProject: () => void;
  onSearch: () => void;
  /** 「设置」那一行:打开设置整页(照 ZCode,track opendesign-zcode-model-settings;原弹层各项搬进「常规」)。 */
  onOpenSettings: () => void;
  desktopShell: boolean;
  updateState: DesktopUpdateState;
  onInstallUpdate: () => void;
};

function dotClass(p: Project, current: boolean): string {
  if (current) return "dot now";
  if (p.delivered) return "dot done";
  if (p.open_count > 0) return "dot open";
  return "dot idle";
}

// 圆点语义(⑩ 小圆点没有图例):hover 时给一句解释,新用户不用猜颜色。
function dotTitle(p: Project, current: boolean): string {
  if (current) return "当前查看的项目";
  if (p.delivered) return "已交付";
  if (p.open_count > 0) return `${p.open_count} 条待办未结`;
  return "暂无待办";
}

export default function Sidebar({
  route, projects, stages, selectedKey, onSelectProject, todosOpenCount, excludedStructural,
  onOpenSettings,
  sessions, sessionProjects, threadKeys, pinnedKeys, titleOverrides,
  onOpenSession, onDeleteSession, onPinSession, onRenameSession, onNewChat, onNewProject,
  onSearch, desktopShell, updateState, onInstallUpdate,
}: Props) {

  // 项目按阶段分堆(T3,用户 07-28 拍板)。折叠状态**落 localStorage**:待办页的
  // toggled 是 useState、刷新即忘,这里不重蹈覆辙(判据 D 段钉死)。
  const groups = useMemo(() => groupProjectsByStage(projects, stages), [projects, stages]);
  const [stagePrefs, setStagePrefs] = useState<StagePrefs>(() =>
    loadStagePrefs(typeof localStorage === "undefined"
      ? null : localStorage.getItem(SIDE_STAGE_STORAGE_KEY)));

  const writeStagePrefs = (next: StagePrefs) => {
    setStagePrefs(next);
    try { localStorage.setItem(SIDE_STAGE_STORAGE_KEY, JSON.stringify(next)); }
    catch { /* 隐私模式:记不住就算了,不该让侧栏崩 */ }
  };

  // 从别处选中的项目(待办「去项目 →」/ 搜索直达)若落在收着的堆里,把那堆展开。
  // 只在**选中项变了**的那一次做:写成渲染期覆盖、或每次 prefs 变都重算,
  // 都会让"选中着的那堆"收不起来 —— 折叠键变死键(判据 E 段最后一条钉死)。
  const revealedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedKey || revealedFor.current === selectedKey) return;
    const g = groups.find((x) => x.projects.some((p) => p.key === selectedKey));
    if (!g) return; // 项目列表还没到:不记账,等它到了再试
    revealedFor.current = selectedKey;
    const next = revealStage(stagePrefs, g);
    if (next !== stagePrefs) writeStagePrefs(next);
  }, [selectedKey, groups, stagePrefs]);

  // ---- 历史对话 ----
  const [view, setView] = useState<SideView>(() => {
    try { return localStorage.getItem(SIDE_VIEW_STORAGE_KEY) === "project" ? "project" : "time"; }
    catch { return "time"; }
  });
  const writeView = (v: SideView) => {
    setView(v);
    try { localStorage.setItem(SIDE_VIEW_STORAGE_KEY, v); } catch { /* 记不住就算了 */ }
  };
  const [timeShown, setTimeShown] = useState(TIME_FIRST);
  const [otherShown, setOtherShown] = useState(LIST_FIRST);
  const [openProj, setOpenProj] = useState<Record<string, boolean>>({});
  const [projShown, setProjShown] = useState<Record<string, number>>({});
  // 同一段对话在按项目视图里可能出现在好几处 ⇒ 菜单 / 改名框按「哪一处 | 哪一段」认,只开在点的那一处
  const [menuId, setMenuId] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; draft: string } | null>(null);
  const renamingRef = useRef<string | null>(null);

  // 菜单开着时:点别处 / Esc 关掉
  useEffect(() => {
    if (!menuId) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Element | null;
      if (!t?.closest?.(".hist-pop, .hist-menu")) setMenuId(null);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuId(null); };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuId]);

  const nameOf = useMemo(() => {
    const m = new Map(projects.map((p) => [p.key, displayProjectName(p.name || p.key)]));
    return (k: string) => m.get(k) ?? k;
  }, [projects]);
  const pinnedSet = useMemo(() => new Set(pinnedKeys), [pinnedKeys]);
  const pinnedList = useMemo(
    () => byRecent((sessions ?? []).filter((s) => pinnedSet.has(s.key))),
    [sessions, pinnedSet],
  );
  const unpinnedCount = (sessions ?? []).length - pinnedList.length;
  const pv = useMemo(
    () => projectView(sessions ?? [], (k) => sessionProjects[k] ?? [], pinnedKeys, threadKeys),
    [sessions, sessionProjects, pinnedKeys, threadKeys],
  );

  const startRename = (id: string, s: SessionItem) => {
    setMenuId(null);
    renamingRef.current = id;
    setRenaming({ id, draft: displayTitle(s, titleOverrides) });
  };
  // Enter 与失焦都走这里;renamingRef 防 Enter 之后卸载那一下的失焦再存一遍
  const finishRename = (s: SessionItem, id: string, save: boolean, draft: string) => {
    if (renamingRef.current !== id) return;
    renamingRef.current = null;
    setRenaming(null);
    if (!save) return;
    const t = cleanRename(draft);
    if (t !== null && t !== displayTitle(s, titleOverrides)) onRenameSession(s, t);
  };

  const histRow = (s: SessionItem, where: string, tag: { text: string; all: string } | null = null) => {
    const id = `${where}|${s.key}`;
    const title = displayTitle(s, titleOverrides);
    if (renaming?.id === id) {
      return (
        <div className="hist-item" key={s.key}>
          <input
            className="hist-rename"
            data-ui="hist-rename-input"
            autoFocus
            maxLength={200}
            value={renaming.draft}
            aria-label="对话的新名字"
            onChange={(e) => setRenaming({ id, draft: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); finishRename(s, id, true, e.currentTarget.value); }
              else if (e.key === "Escape") { e.preventDefault(); finishRename(s, id, false, ""); }
            }}
            onBlur={(e) => finishRename(s, id, true, e.currentTarget.value)}
          />
        </div>
      );
    }
    const pinned = pinnedSet.has(s.key);
    const open = menuId === id;
    return (
      <div className={`hist-item${open ? " menu-open" : ""}`} key={s.key}>
        <button className="hist-row" title={title} onClick={() => onOpenSession(s)}>
          <span className="t">{title}</span>
          {tag && <span className="hist-proj" title={tag.all}>{tag.text}</span>}
          <span className="when">{relTime(s.updated_at)}</span>
          {/* span 非嵌套 button(HTML 不允许);阻冒泡免触发续聊 */}
          <span
            className="hist-menu"
            role="button"
            data-ui="hist-menu"
            title="置顶 / 改名 / 删除"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={(e) => {
              e.stopPropagation();
              setMenuId(open ? null : id);
            }}
          >
            ⋯
          </span>
        </button>
        {open && (
          <div className="hist-pop" role="menu" data-ui="hist-pop">
            <button role="menuitem" data-ui="hist-pin"
                    onClick={() => { setMenuId(null); onPinSession(s, !pinned); }}>
              {pinned ? "取消置顶" : "置顶"}
            </button>
            <button role="menuitem" data-ui="hist-rename" onClick={() => startRename(id, s)}>改名</button>
            <button role="menuitem" className="danger" data-ui="hist-delete"
                    onClick={() => { setMenuId(null); onDeleteSession(s); }}>
              删除
            </button>
          </div>
        )}
      </div>
    );
  };
  // 小标只写第一个 +N;悬停列出全部(QA DeepSeek / GLM:「翡翠湾-1801 +1」看不出另一个是哪个)
  const tagOf = (key: string) => {
    const keys = sessionProjects[key] ?? [];
    const text = firstTag(keys, nameOf);
    return text ? { text, all: `碰过的项目:${keys.map(nameOf).join("、")}` } : null;
  };
  const moreBtn = (onMore: () => void) => (
    <button className="side-more" data-ui="side-more" onClick={onMore}>显示更多</button>
  );

  const projRow = (p: Project) => {
    const current = p.key === selectedKey;
    // 白底卡片当前态只在 2a(workspace)呈现;3a 等页选中项目仅保留赤陶圆点
    const card = current && route === "workspace";
    const row = (
      <button
        key={p.key}
        className={`proj-row${card ? " current" : ""}${p.delivered ? " delivered" : ""}${p.unregistered ? " unregistered" : ""}`}
        onClick={() => onSelectProject(p.key)}
        title={p.unregistered
          ? `${p.name} · 工作区文件夹(未建档)——在对话里说「新建项目」即可建档`
          : p.stage ? `${p.name} · 阶段:${p.stage}` : p.name}
      >
        <span className="ico-col">
          <span className={dotClass(p, current)} title={dotTitle(p, current)} />
        </span>
        <span className="nm">{displayProjectName(p.name)}</span>
        {p.group ? <span className="n-group">{p.group}</span> : null}
        {p.unregistered ? null : (
          p.open_count > 0 && <span className="n-open">{p.open_count}</span>
        )}
      </button>
    );
    if (view !== "project" || sessions === null) return row;
    // 按项目:项目行照旧(点了进工作区),右边一个「对话数 ▸」展开它的对话
    const list = pv.byProject[p.key] ?? [];
    const expanded = !!openProj[p.key] && list.length > 0;
    const shown = projShown[p.key] ?? LIST_FIRST;
    return (
      <Fragment key={p.key}>
        <div className="proj-item">
          {row}
          {list.length > 0 && (
            <button
              className="proj-expand"
              data-ui="proj-expand"
              data-project={p.key}
              aria-expanded={expanded}
              aria-label={`${expanded ? "收起" : "展开"}这个项目的 ${list.length} 段对话`}
              title={expanded ? "收起这个项目的对话" : `看这个项目的 ${list.length} 段对话`}
              onClick={() => setOpenProj((m) => ({ ...m, [p.key]: !expanded }))}
            >
              {/* 对话图标:和左边的待办数(裸数字)区分开(QA Gemini:「2 2 ▾」分不清哪个是待办、哪个是对话) */}
              <SideIcon name="message-circle" />
              {list.length}<span className="chev">{expanded ? "▾" : "▸"}</span>
            </button>
          )}
        </div>
        {expanded && (
          <div className="side-list proj-sessions" data-ui="proj-sessions" data-project={p.key}>
            {list.slice(0, shown).map((s) => histRow(s, `p:${p.key}`))}
            {list.length > shown
              && moreBtn(() => setProjShown((m) => ({ ...m, [p.key]: shown + MORE_STEP })))}
          </div>
        )}
      </Fragment>
    );
  };

  // 一堆 = 阶段头(共享折叠控件,与待办页同一套折叠语言)+ 展开时的项目行
  const stageGroup = (g: StageGroup) => {
    const open = isStageGroupOpen(g, stagePrefs);
    return (
      <div className="stage-group" data-ui="stage-group" data-stage={g.stage} key={g.stage}>
        <div className="stage-head">
          <GroupToggle
            open={open}
            onToggle={() => writeStagePrefs({ ...stagePrefs, [g.stage]: !open })}
          >
            <span className="nm">{g.stage}</span>
            <span className="n-count">{g.projects.length}</span>
          </GroupToggle>
        </div>
        {open && g.projects.map(projRow)}
      </div>
    );
  };

  return (
    <nav className="side">
      <div className="side-brand">
        <span className="brand">OpenDesign</span>
      </div>

      {/* 全局操作组(v2:无日历行、无快捷键角标;技能收进本组) */}
      <div className="side-group">
        <button
          className={`side-row${route === "home" ? " current" : ""}`}
          data-ui="side-new-chat"
          onClick={onNewChat}
          title="总聊天入口,新项目从对话里创建"
        >
          <SideIcon name="message-circle-plus" />
          <span className="grow">新对话</span>
        </button>
        <button
          className="side-row"
          title="全局精确查找变更/图片,不经过 AI(⌘K)"
          onClick={onSearch}
        >
          <SideIcon name="search" />
          <span className="grow">搜索</span>
        </button>
        <button
          className={`side-row${route === "todos" ? " current" : ""}`}
          onClick={() => { window.location.hash = "#/todos"; }}
          title="汇总所有项目未办结变更"
        >
          <SideIcon name="list-todo" />
          <span className="grow">待办事项</span>
          {todosOpenCount !== null && todosOpenCount > 0 && (
            <span className="count-badge">{todosOpenCount}</span>
          )}
        </button>
        <button
          className={`side-row${route === "skills" ? " current" : ""}`}
          title="CAD 转 3D、PS 合成 PDF 等"
          onClick={() => { window.location.hash = "#/skills"; }}
        >
          <SideIcon name="blocks" />
          <span className="grow">技能</span>
          <span className="chev">›</span>
        </button>
      </div>

      <div className="side-scroll" data-ui="side-scroll">
      {/* 历史对话(修改单 F4:未连接时整组隐藏——sessions===null 即未连接) */}
      {sessions !== null && (
        <>
          <div className="side-sect">
            <span className="sect-title">历史对话</span>
            <span className="grow" />
            <div className="side-view" role="group" aria-label="历史对话怎么排">
              <button data-ui="side-view-time" aria-pressed={view === "time"}
                      className={view === "time" ? "on" : ""} onClick={() => writeView("time")}>
                按时间
              </button>
              <button data-ui="side-view-project" aria-pressed={view === "project"}
                      className={view === "project" ? "on" : ""} onClick={() => writeView("project")}>
                按项目
              </button>
            </div>
          </div>
          {pinnedList.length > 0 && (
            <>
              <div className="side-day">已置顶</div>
              <div className="side-list" data-ui="side-pinned">
                {pinnedList.map((s) => histRow(s, "pin", tagOf(s.key)))}
              </div>
            </>
          )}
          {view === "time" ? (
            <>
              <div className="side-list" data-ui="side-history">
                {timeSections(sessions, new Date(), pinnedKeys, timeShown).map((sec) => (
                  <Fragment key={sec.label}>
                    <div className="side-day" data-ui="side-day">{sec.label}</div>
                    {sec.items.map((s) => histRow(s, "time", tagOf(s.key)))}
                  </Fragment>
                ))}
              </div>
              {unpinnedCount > timeShown && moreBtn(() => setTimeShown((n) => n + MORE_STEP))}
              {sessions.length === 0 && <div className="side-empty-hint">暂无对话</div>}
            </>
          ) : (
            <div className="side-empty-hint">点项目右边的数字,看它的对话</div>
          )}
        </>
      )}

      {/* 项目 */}
      <div className="side-sect projects">
        <span className="sect-title">项目</span>
        <span className="sect-count">{projects.length}</span>
        <span className="grow" />
        <button className="sect-add" title="新建项目(在对话里说「新建项目…」)" onClick={onNewProject}>
          +
        </button>
      </div>
      <div className="proj-list">
        {groups.map(stageGroup)}
        {projects.length === 0 && (
          <div className="side-empty-hint">还没有项目——在对话里说「新建项目…」</div>
        )}
        {/* 被"猜"成结构目录而没列出来的,要说一声(-p2 四审:静默排除 = 用户觉得
            文件夹不见了,而他不会去翻配置)。自己在配置里声明过的不再啰嗦。 */}
        {excludedStructural && excludedStructural.length > 0 && (
          <div className="side-empty-hint" data-ui="excluded-structural"
               title="这些文件夹没有列进项目列表。到右边的「工作区文件夹」卡片里可以改。">
            {excludedStructural.join("、")} 没列进项目列表
            <span className="side-hint-cta">
              {/* 体检卡 2026-07-28 挪进设置后,这句是唯一把人带到纠正入口的指路 ——
                  它要是还指着"右边卡片",入口就等于不存在了(判据钉了这条)。 */}
              少了你的项目?到左下角「设置 → 工作区文件夹」里改
            </span>
          </div>
        )}
      </div>

      {/* 按项目:没碰过任何项目的对话 */}
      {view === "project" && sessions !== null && pv.other.length > 0 && (
        <>
          <div className="side-sect">
            <span className="sect-title">其他对话</span>
            <span className="sect-count">{pv.other.length}</span>
          </div>
          <div className="side-list" data-ui="side-other">
            {pv.other.slice(0, otherShown).map((s) => histRow(s, "other"))}
          </div>
          {pv.other.length > otherShown && moreBtn(() => setOtherShown((n) => n + MORE_STEP))}
        </>
      )}
      </div>

      <div className="side-footer">
        <div className="side-row settings-toggle-row">
          <button data-ui="settings-toggle" onClick={onOpenSettings} aria-expanded={false}>
            <SideIcon name="settings" />
            <span className="grow">设置</span>
            {hasDesktopUpdateBadge(updateState) && <span className="update-dot" data-ui="update-badge">●</span>}
            <span className="chev">›</span>
          </button>
          {desktopShell && showRestart(updateState) && (
            <button className="side-update-restart" data-ui="update-restart" onClick={onInstallUpdate}>
              重启以更新 <small>{RESTART_HINT}</small>
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
