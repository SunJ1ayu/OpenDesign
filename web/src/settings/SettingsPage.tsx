// 设置整页(照 ZCode 设置页:左栏目 + 右内容;track opendesign-zcode-model-settings)。
// 进来时整条侧栏换成设置栏目:「← 返回工作区」/ 常规 / 模型设置。聊天实例照常驻(App 只把它们藏起来,不卸载)。
//
// 🔴 钩子沿用(云 E4 与 tests/e2e/desktop_update.e2e.mjs 不改):「返回工作区」就是 `settings-toggle`
//    (aria-expanded=true,点它回去);常规页原样放旧弹层的各项,更新那几个钩子 update-status / update-check /
//    update-retry 都在这里;下好更新后「重启以更新」与「约 2 分钟」提示也在这里(弹层时代同款)。
import {
  desktopUpdateLabel,
  RESTART_HINT,
  showCheck,
  showRestart,
  showRetry,
} from "../desktopUpdate";
import type { DesktopUpdateState } from "../desktopShell";
import { RELEASES_PAGE } from "../update";
import type { ConsentMode } from "../api";
import { useState } from "react";
import { applyTheme, loadThemePref, type ThemePref } from "../theme";
import { SideIcon, type SideIconName } from "../workspace/icons";
import ModelSettings from "./ModelSettings";
import type { SettingsSection } from "./modelSettings";

type Props = {
  section: SettingsSection;
  provider: string | null;
  onBack: () => void;
  onNavigate: (section: SettingsSection, provider?: string | null) => void;
  onOpenFolderVisibility: () => void;
  /** 现在接的项目文件夹(没接 ⇒ null)与"更换"入口(track opendesign-workspace-picker)。 */
  workspaceRoot: string | null;
  onPickWorkspace: () => void;
  consentMode: ConsentMode | null;
  onSetConsentMode: (mode: ConsentMode) => void;
  health: { version: string; ds_root: string; model: string | null } | null;
  desktopShell: boolean;
  updateState: DesktopUpdateState;
  onCheckUpdate: () => void;
  onInstallUpdate: () => void;
};

/** 外观三档(照 ZCode THEME_OPTIONS:跟随系统 Monitor / 深色 Moon / 浅色 Sun)。 */
const THEMES: { pref: ThemePref; label: string; icon: SideIconName }[] = [
  { pref: "dark", label: "深色", icon: "moon" },
  { pref: "light", label: "浅色", icon: "sun" },
  { pref: "system", label: "跟随系统", icon: "monitor" },
];

function Appearance() {
  const [pref, setPref] = useState<ThemePref>(() => loadThemePref());
  return (
    <div className="settings-item" data-ui="settings-appearance">
      <span className="lbl">外观</span>
      <span className="seg theme-seg" role="radiogroup" aria-label="外观">
        {THEMES.map((t) => (
          <button key={t.pref} type="button" role="radio" aria-checked={pref === t.pref}
            data-theme-opt={t.pref} className={`opt${pref === t.pref ? " on" : ""}`}
            onClick={() => { applyTheme(t.pref); setPref(t.pref); }}>
            <SideIcon name={t.icon} />{t.label}
          </button>
        ))}
      </span>
    </div>
  );
}

function General(p: Props) {
  const { consentMode, onSetConsentMode, health, desktopShell, updateState, onCheckUpdate, onInstallUpdate } = p;
  return (
    <section className="settings-general" data-ui="settings-general">
      <h2>常规</h2>
      <div className="settings-list">
        <Appearance />
        <div className="settings-item">
          <span className="lbl">数据与备份</span>
          <span className="val mono">{health ? health.ds_root : "~/OpenDesign"}</span>
        </div>
        {/* 手动选工作区(track opendesign-workspace-picker):以前只能靠助手设,接好之后界面上没有地方换 */}
        <button className="settings-item" data-ui="settings-workspace-root"
          title="选你电脑上放项目的那个文件夹" onClick={p.onPickWorkspace}>
          <span className="lbl">项目文件夹</span>
          <span className="val">
            {p.workspaceRoot
              ? <><span className="mono">{p.workspaceRoot}</span> · 更换 ›</>
              : "还没接入 · 选择 ›"}
          </span>
        </button>
        <button className="settings-item" data-ui="settings-folder-visibility"
          title="选哪些文件夹要出现在左边的项目列表里" onClick={p.onOpenFolderVisibility}>
          <span className="lbl">工作区文件夹</span>
          <span className="val">哪些算项目 ›</span>
        </button>
        {/* 业主同意闸的档位(track opendesign-owner-consent):**全机唯一能改这个档位的入口**。
            关掉是降低安全性的动作,所以只有关的方向要二次确认(开不用)。 */}
        <button
          className="settings-item"
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
            {consentMode === null ? "…" : consentMode === "ask" ? "每次问我 ›" : "不用问 ›"}
          </span>
        </button>
        <div className="settings-item" title="⌘N 新对话 · ⌘K 搜索">
          <span className="lbl">快捷键</span>
          <span className="val mono">⌘N 新对话 · ⌘K 搜索</span>
        </div>
      </div>

      <h2>软件更新</h2>
      <div className="settings-list">
        {desktopShell ? (
          <>
            <div className="settings-item">
              <span className="lbl">当前状态</span>
              <span className="val mono" data-ui="update-status">
                {desktopUpdateLabel(updateState, health?.version ?? "未知")}
              </span>
            </div>
            {showCheck(updateState) && (
              <button className="settings-item" data-ui="update-check" onClick={onCheckUpdate}>
                <span className="lbl">检查更新</span>
              </button>
            )}
            {showRetry(updateState) && (
              <button className="settings-item" data-ui="update-retry" onClick={onCheckUpdate}>
                <span className="lbl">重试</span>
              </button>
            )}
            {showRestart(updateState) && (
              <button className="settings-item accent" onClick={onInstallUpdate}>
                <span className="lbl">重启以更新</span>
                <span className="val">{RESTART_HINT}</span>
              </button>
            )}
          </>
        ) : (
          <a className="settings-item" href={RELEASES_PAGE} target="_blank" rel="noreferrer">
            <span className="lbl" data-ui="update-status">当前版本 v{health?.version ?? "未知"}</span>
            <span className="val">发布页 ›</span>
          </a>
        )}
      </div>
    </section>
  );
}

export default function SettingsPage(props: Props) {
  const { section, provider, onBack, onNavigate } = props;
  return (
    <>
      <nav className="side settings-nav" data-ui="settings-nav" aria-label="设置">
        <div className="side-group">
          <button className="side-row settings-back" data-ui="settings-toggle" aria-expanded={true} onClick={onBack}>
            <SideIcon name="arrow-left" />
            <span className="grow">返回工作区</span>
          </button>
        </div>
        <div className="settings-nav-title">设置</div>
        <div className="side-group">
          <button className={`side-row${section === "general" ? " current" : ""}`} data-ui="settings-nav-general"
            aria-current={section === "general" ? "page" : undefined} onClick={() => onNavigate("general")}>
            <SideIcon name="settings-2" />
            <span className="grow">常规</span>
          </button>
          <button className={`side-row${section === "models" ? " current" : ""}`} data-ui="settings-nav-models"
            aria-current={section === "models" ? "page" : undefined} onClick={() => onNavigate("models")}>
            <SideIcon name="package" />
            <span className="grow">模型设置</span>
          </button>
        </div>
      </nav>
      <main className="settings-page" data-ui="settings-page">
        <div className="settings-inner">
          {section === "general" ? (
            <General {...props} />
          ) : (
            <ModelSettings provider={provider} onSelectProvider={(id) => onNavigate("models", id)} />
          )}
        </div>
      </main>
    </>
  );
}
