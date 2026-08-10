import { useEffect, useMemo, useRef, useState } from "react";
import type { ConsentMode, Project } from "../api";
import { relTime } from "../api";
import { displayProjectName } from "./projectName";
import GroupToggle from "../GroupToggle";
import {
  groupProjectsByStage, isStageGroupOpen, loadStagePrefs, revealStage,
  SIDE_STAGE_STORAGE_KEY, type StageGroup, type StagePrefs,
} from "./projectGroups";

// 左侧栏 v2(P3 T3,handoff §1,240px):品牌 / 全局操作组(新对话/搜索/
// 待办事项/技能)/ 历史对话 / 项目 / 设置弹层。图标沿用定稿的 Unicode 占位
// (✳ ⌕ ◎ ✦ ◷ ⚙)。v2 要点:日历行删除(功能将来融进待办页)、技能上移进
// 全局操作组、快捷键角标(⌘N/⌘K)从 UI 移除(keydown 行为在 App 保留)、
// 所有行共用 16px 图标列居中对齐;全局操作组按路由呈当前态(新对话=home、
// 待办事项=todos、技能=skills;搜索是弹层无路由不设),
// 项目行的白底卡片当前态只在 workspace 路由呈现(t3 画板:3a 下项目行均普通态,
// 仅选中项目圆点保持赤陶)。

export type SessionItem = { key: string; title?: string; preview?: string; updated_at?: string };

type Props = {
  route: "home" | "workspace" | "todos" | "skills" | "gallery";
  projects: Project[];
  /** 阶段词表(/api/projects 下发,单一真相源 = 后端 PROJECT_STAGES):项目分堆的排序依据 */
  stages: string[];
  selectedKey: string | null;
  onSelectProject: (key: string) => void;
  todosOpenCount: number | null;
  sessions: SessionItem[] | null; // null = 未连接/不可用(隐藏区块内容)
  /** -p2:被"猜"成结构目录、因此没进列表的文件夹名(显式声明的不报) */
  excludedStructural?: string[];
  /** project-thread:sessionKey → 项目显示名(命中项目映射的会话加小标) */
  sessionTags?: Record<string, string>;
  onOpenSession: (s: SessionItem) => void; // p6:点历史行 → 首页 attach 续聊
  onDeleteSession: (s: SessionItem) => void; // p7:悬停 ✕,确认在 App 层
  onNewChat: () => void;
  onNewProject: () => void;
  onSearch: () => void;
  /** 设置弹层里的「工作区文件夹」入口(体检卡 2026-07-28 挪进设置,浮层由 App 渲染)。 */
  onOpenFolderVisibility: () => void;
  /** 业主同意闸档位(track opendesign-owner-consent)。null = 还没拉到。 */
  consentMode: ConsentMode | null;
  onSetConsentMode: (mode: ConsentMode) => void;
  health: { version: string; ds_root: string; model: string | null } | null;
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
  onOpenFolderVisibility, consentMode, onSetConsentMode,
  sessions, sessionTags, onOpenSession, onDeleteSession, onNewChat, onNewProject,
  onSearch, health,
}: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);

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

  // 弹层外点击收起(设置行自身的 toggle 在 onClick 里处理)
  useEffect(() => {
    if (!settingsOpen) return;
    const onDown = (e: MouseEvent) => {
      const el = e.target as Element | null;
      // 弹层内与设置行自身不算"外":设置行的 toggle 自己管开合
      if (el && el.closest(".settings-pop, .side-footer")) return;
      setSettingsOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [settingsOpen]);

  // 全局原则(修改单 A3):esc 关一切弹层——设置弹层也不例外。
  useEffect(() => {
    if (!settingsOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen]);

  const recent = (sessions ?? []).slice(0, 2);

  const projRow = (p: Project) => {
    const current = p.key === selectedKey;
    // 白底卡片当前态只在 2a(workspace)呈现;3a 等页选中项目仅保留赤陶圆点
    const card = current && route === "workspace";
    return (
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
        <span className="brand">
          OpenDesign<em>.</em>
        </span>
      </div>

      {/* 全局操作组(v2:无日历行、无快捷键角标;技能收进本组) */}
      <div className="side-group">
        <button
          className={`side-row${route === "home" ? " current" : ""}`}
          data-ui="side-new-chat"
          onClick={onNewChat}
          title="总聊天入口,新项目从对话里创建"
        >
          <span className="ico terra">✳</span>
          <span className="grow">新对话</span>
        </button>
        <button
          className="side-row"
          title="全局精确查找变更/图片,不经过 AI(⌘K)"
          onClick={onSearch}
        >
          <span className="ico">⌕</span>
          <span className="grow">搜索</span>
        </button>
        <button
          className={`side-row${route === "todos" ? " current" : ""}`}
          onClick={() => { window.location.hash = "#/todos"; }}
          title="汇总所有项目未办结变更"
        >
          <span className="ico">◎</span>
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
          <span className="ico">✦</span>
          <span className="grow">技能</span>
          <span className="chev">›</span>
        </button>
      </div>

      {/* 历史对话(修改单 F4:未连接时整组隐藏——sessions===null 即未连接) */}
      {sessions !== null && (
        <>
          <div className="side-sect">
            <span className="sect-title">历史对话</span>
            <span className="grow" />
            <button className="sect-link" title="全部对话(即将支持)">全部</button>
          </div>
          <div className="side-list">
            {recent.map((s) => (
              <button
                className="hist-row"
                key={s.key}
                title={s.title || s.preview || ""}
                onClick={() => onOpenSession(s)}
              >
                <span className="ico">◷</span>
                <span className="t">{s.title || s.preview || "(未命名对话)"}</span>
                {sessionTags?.[s.key] && <span className="hist-proj">{sessionTags[s.key]}</span>}
                <span className="when">{relTime(s.updated_at)}</span>
                {/* span 非嵌套 button(HTML 不允许);阻冒泡免触发续聊 */}
                <span
                  className="hist-del"
                  role="button"
                  title="删除对话"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(s);
                  }}
                >
                  ✕
                </span>
              </button>
            ))}
            {recent.length === 0 && <div className="side-empty-hint">暂无对话</div>}
          </div>
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

      <div className="side-flex" />

      {/* 设置弹层(向上弹出;唯一的原型交互) */}
      {settingsOpen && (
        <div className="settings-pop">
          <button className="item" title="定稿仅浅色;深色适配排期中">
            <span className="lbl">外观</span>
            <span className="val">浅色 ▾</span>
            <span className="soon">深色即将支持</span>
          </button>
          <button
            className="item"
            title="切换模型:python bin/set_model.py <模型id>,然后重启 gateway"
          >
            <span className="lbl">AI 模型</span>
            <span className="val mono">{health?.model ?? "未连接"}</span>
          </button>
          <button className="item">
            <span className="lbl">数据与备份</span>
            <span className="val mono">{health ? health.ds_root : "~/OpenDesign"}</span>
          </button>
          <button
            className="item"
            data-ui="settings-folder-visibility"
            title="选哪些文件夹要出现在左边的项目列表里"
            onClick={() => {
              setSettingsOpen(false);
              onOpenFolderVisibility();
            }}
          >
            <span className="lbl">工作区文件夹</span>
            <span className="val">哪些算项目 ›</span>
          </button>
          {/* 业主同意闸的档位(track opendesign-owner-consent)。
              业主原话:「让用户选择弹或者都不弹,就像 Claude Code 和 Codex 这些 agent」。
              **这里是全机唯一能改这个档位的入口** —— 任何 MCP 工具都写不了
              config/consent.json,判据 O5 从工具表真相源枚举 33 个工具逐个真调验过。
              关掉是降低安全性的动作,所以只有关的方向要二次确认(开不用)。 */}
          <button
            className="item"
            data-ui="settings-consent-mode"
            title="助手想扩大它能看到的文件范围时(改工作区根、绑项目文件夹),要不要先问你"
            onClick={() => {
              if (consentMode === null) return;
              const next = consentMode === "ask" ? "allow" : "ask";
              if (next === "allow" && !window.confirm(
                "关掉之后,助手改工作区根目录、绑定项目文件夹**不再问你**,立即生效。\n\n"
                + "这意味着:它读到的一份文档里如果藏了指令,就可能让它把工作区指到别处、"
                + "读走那边的资料,而你不会看到任何提示。\n\n确定要关掉吗?")) return;
              onSetConsentMode(next);
            }}
          >
            <span className="lbl">危险动作确认</span>
            <span className="val">
              {consentMode === null ? "…"
                : consentMode === "ask" ? "每次问我 ›" : "不用问 ›"}
            </span>
          </button>
          <button className="item" title="⌘N 新对话 · ⌘K 搜索">
            <span className="lbl">快捷键</span>
          </button>
          <div className="divider" />
          <button className="item">
            <span className="lbl muted">检查更新</span>
            <span className="val mono faint">
              {health ? `ds-web v${health.version}` : "服务离线"}
            </span>
          </button>
        </div>
      )}
      <div className="side-footer">
        <button
          className="side-row"
          onClick={() => setSettingsOpen((v) => !v)}
          aria-expanded={settingsOpen}
        >
          <span className="ico">⚙</span>
          <span className="grow">设置</span>
          <span className="chev">{settingsOpen ? "▴" : "▾"}</span>
        </button>
      </div>
    </nav>
  );
}
