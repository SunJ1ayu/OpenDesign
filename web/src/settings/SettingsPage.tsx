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
import ModelSettings from "./ModelSettings";
import type { SettingsSection } from "./modelSettings";

type Props = {
  section: SettingsSection;
  provider: string | null;
  onBack: () => void;
  onNavigate: (section: SettingsSection, provider?: string | null) => void;
  onOpenFolderVisibility: () => void;
  consentMode: ConsentMode | null;
  onSetConsentMode: (mode: ConsentMode) => void;
  health: { version: string; ds_root: string; model: string | null } | null;
  desktopShell: boolean;
  updateState: DesktopUpdateState;
  onCheckUpdate: () => void;
  onInstallUpdate: () => void;
};

function Icon({ d }: { d: string }) {
  return (
    <svg className="ico" viewBox="0 0 24 24" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
const ARROW_LEFT = "M19 12H5M12 19l-7-7 7-7";
const SLIDERS = "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6";
const PACKAGE = "M16.5 9.4 7.55 4.24M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96 12 12.01l8.73-5.05M12 22.08V12";

function General(p: Props) {
  const { consentMode, onSetConsentMode, health, desktopShell, updateState, onCheckUpdate, onInstallUpdate } = p;
  return (
    <section className="settings-general" data-ui="settings-general">
      <h2>常规</h2>
      <div className="settings-list">
        <div className="settings-item" title="定稿仅浅色;深色适配排期中">
          <span className="lbl">外观</span>
          <span className="val">浅色 <span className="soon">深色即将支持</span></span>
        </div>
        <div className="settings-item">
          <span className="lbl">数据与备份</span>
          <span className="val mono">{health ? health.ds_root : "~/OpenDesign"}</span>
        </div>
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
            <Icon d={ARROW_LEFT} />
            <span className="grow">返回工作区</span>
          </button>
        </div>
        <div className="settings-nav-title">设置</div>
        <div className="side-group">
          <button className={`side-row${section === "general" ? " current" : ""}`} data-ui="settings-nav-general"
            aria-current={section === "general" ? "page" : undefined} onClick={() => onNavigate("general")}>
            <Icon d={SLIDERS} />
            <span className="grow">常规</span>
          </button>
          <button className={`side-row${section === "models" ? " current" : ""}`} data-ui="settings-nav-models"
            aria-current={section === "models" ? "page" : undefined} onClick={() => onNavigate("models")}>
            <Icon d={PACKAGE} />
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
