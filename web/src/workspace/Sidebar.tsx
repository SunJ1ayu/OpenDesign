import { useEffect, useRef, useState } from "react";
import type { Project } from "../api";
import { relTime } from "../api";

// 左侧栏 v2(P3 T3,handoff §1,240px):品牌 / 全局操作组(新对话/搜索/
// 待办事项/技能)/ 历史对话 / 项目 / 设置弹层。图标沿用定稿的 Unicode 占位
// (✳ ⌕ ◎ ✦ ◷ ⚙)。v2 要点:日历行删除(功能将来融进待办页)、技能上移进
// 全局操作组、快捷键角标(⌘N/⌘K)从 UI 移除(keydown 行为在 App 保留)、
// 所有行共用 16px 图标列居中对齐;「新对话」在 home 路由呈当前态,
// 项目行的白底卡片当前态只在 workspace 路由呈现(t3 画板:3a 下项目行均普通态,
// 仅选中项目圆点保持赤陶)。

export type SessionItem = { key: string; title?: string; preview?: string; updated_at?: string };

type Props = {
  route: "home" | "workspace" | "todos" | "skills";
  projects: Project[];
  selectedKey: string | null;
  onSelectProject: (key: string) => void;
  todosOpenCount: number | null;
  sessions: SessionItem[] | null; // null = 未连接/不可用(隐藏区块内容)
  onNewChat: () => void;
  onNewProject: () => void;
  health: { version: string; ds_root: string } | null;
};

function dotClass(p: Project, current: boolean): string {
  if (current) return "dot now";
  if (p.delivered) return "dot done";
  if (p.open_count > 0) return "dot open";
  return "dot idle";
}

export default function Sidebar({
  route, projects, selectedKey, onSelectProject, todosOpenCount,
  sessions, onNewChat, onNewProject, health,
}: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const popRef = useRef<HTMLDivElement>(null);

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

  const recent = (sessions ?? []).slice(0, 2);

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
          onClick={onNewChat}
          title="总聊天入口,新项目从对话里创建"
        >
          <span className="ico terra">✳</span>
          <span className="grow">新对话</span>
        </button>
        <button className="side-row" title="全局搜索(即将支持)">
          <span className="ico">⌕</span>
          <span className="grow">搜索</span>
        </button>
        <button
          className="side-row"
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
          className="side-row"
          title="CAD 转 3D、PS 合成 PDF 等"
          onClick={() => { window.location.hash = "#/skills"; }}
        >
          <span className="ico">✦</span>
          <span className="grow">技能</span>
          <span className="chev">›</span>
        </button>
      </div>

      {/* 历史对话 */}
      <div className="side-sect">
        <span className="sect-title">历史对话</span>
        <span className="grow" />
        <button className="sect-link" title="全部对话(即将支持)">全部</button>
      </div>
      <div className="side-list">
        {recent.map((s) => (
          <button className="hist-row" key={s.key} title={s.title || s.preview || ""}>
            <span className="ico">◷</span>
            <span className="t">{s.title || s.preview || "(未命名对话)"}</span>
            <span className="when">{relTime(s.updated_at)}</span>
          </button>
        ))}
        {sessions !== null && recent.length === 0 && (
          <div className="side-empty-hint">还没有对话记录</div>
        )}
        {sessions === null && (
          <div className="side-empty-hint">连接聊天后显示</div>
        )}
      </div>

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
        {projects.map((p) => {
          const current = p.key === selectedKey;
          // 白底卡片当前态只在 2a(workspace)呈现;3a 等页选中项目仅保留赤陶圆点
          const card = current && route === "workspace";
          return (
            <button
              key={p.key}
              className={`proj-row${card ? " current" : ""}${p.delivered ? " delivered" : ""}`}
              onClick={() => onSelectProject(p.key)}
              title={p.stage ? `阶段:${p.stage}` : undefined}
            >
              <span className="ico-col">
                <span className={dotClass(p, current)} />
              </span>
              <span className="nm">{p.name}</span>
              {p.open_count > 0 && <span className="n-open">{p.open_count}</span>}
            </button>
          );
        })}
        {projects.length === 0 && (
          <div className="side-empty-hint">还没有项目——在对话里说「新建项目…」</div>
        )}
      </div>

      <div className="side-flex" />

      {/* 设置弹层(向上弹出;唯一的原型交互) */}
      {settingsOpen && (
        <div className="settings-pop" ref={popRef}>
          <button className="item" title="定稿仅浅色;深色适配排期中">
            <span className="lbl">外观</span>
            <span className="val">浅色 ▾</span>
            <span className="soon">深色即将支持</span>
          </button>
          <button className="item" title="模型与通道设置在 nanobot 配置里">
            <span className="lbl">AI 模型</span>
            <span className="val">本地默认 ▾</span>
          </button>
          <button className="item">
            <span className="lbl">数据与备份</span>
            <span className="val mono">{health ? health.ds_root : "~/OpenDesign"}</span>
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
