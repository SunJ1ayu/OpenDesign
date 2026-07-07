import { useEffect, useState } from "react";
import TodoPage from "./TodoPage";

// lucide 风格内联图标(nanobot 同款图标系:24 viewBox/描边2/16px 渲染)
const ICONS: Record<string, JSX.Element> = {
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  todos: (
    <>
      <rect x="3" y="5" width="6" height="6" rx="1" />
      <path d="m3 17 2 2 4-4" />
      <path d="M13 6h8" />
      <path d="M13 12h8" />
      <path d="M13 18h8" />
    </>
  ),
  calendar: (
    <>
      <path d="M8 2v4" />
      <path d="M16 2v4" />
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M3 10h18" />
    </>
  ),
  toolbox: (
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  ),
  settings: (
    <>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
};

function Icon({ name }: { name: string }) {
  return (
    <svg
      className="nav-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  );
}

// 侧栏 = plan v2 的固定五项(IA 判据:常驻视图独立页,一次性动作进工具箱)。
// 聊天是首屏门面,T5 换成真聊天;日历 P2;工具箱先占位卡片,不做插件框架。
// 设置钉在左下角(nanobot 同位);hint 收进 title 提示,行高与 nanobot 对齐。
const MODULES = [
  { key: "chat", label: "聊天", hint: "工作台门面 · 直连 nanobot" },
  { key: "todos", label: "待办", hint: "未关闭变更与超期项目" },
  { key: "calendar", label: "日历", hint: "P2 · 排期与重要提醒" },
  { key: "toolbox", label: "工具箱", hint: "跑完就走的小工具" },
] as const;

const SETTINGS = { key: "settings", label: "设置", hint: "外观与服务状态" } as const;

const ALL = [...MODULES, SETTINGS] as const;
type ModuleKey = (typeof ALL)[number]["key"];

function fromHash(): ModuleKey {
  const h = window.location.hash.replace("#/", "");
  return (ALL.some((m) => m.key === h) ? h : "chat") as ModuleKey;
}

// 深浅模式:默认跟系统(auto),手动选择存 localStorage;.dark 打在 <html> 上
// —— 与 nanobot 同机制,token 两套变量见 app.css。
type Theme = "auto" | "light" | "dark";

function applyTheme(t: Theme) {
  const dark =
    t === "dark" ||
    (t === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem("ds-theme") as Theme) || "auto",
  );
  useEffect(() => {
    applyTheme(theme);
    if (theme !== "auto") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("auto");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);
  const set = (t: Theme) => {
    localStorage.setItem("ds-theme", t);
    setTheme(t);
  };
  return [theme, set];
}

function Placeholder({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="placeholder">
      <h2>{title}</h2>
      {lines.map((l) => (
        <p key={l}>{l}</p>
      ))}
    </div>
  );
}

// 聊天占位:壳按最终布局立起来(消息区+输入条),T4/T5 填内容
function ChatPage() {
  return (
    <div className="chat-shell">
      <div className="chat-empty">
        <p>聊天正在收进工作台(下一轮交付)。</p>
        <p>
          现在请用{" "}
          <a href="http://127.0.0.1:8765/" target="_blank" rel="noreferrer">
            nanobot 原版界面（127.0.0.1:8765）
          </a>
        </p>
      </div>
      <div className="chat-inputbar">给 OpenDesign 发消息…（即将可用）</div>
    </div>
  );
}

const TOOLS = [
  {
    name: "图片规整",
    desc: "把不同长宽的图片批量统一宽度/分辨率,输出新目录副本,不动原图。",
    stage: "P3",
  },
  {
    name: "3D 查看",
    desc: "户型 CAD→3D 模型查看。",
    stage: "P4",
  },
] as const;

function ToolboxPage() {
  return (
    <div>
      <h2>工具箱</h2>
      <p className="muted">
        一次性动作类小工具都住这里,想到新的往里加卡片,侧栏保持不长。
      </p>
      <div className="toolbox-grid">
        {TOOLS.map((t) => (
          <div key={t.name} className="tool-card disabled">
            <div className="tool-name">{t.name}</div>
            <div className="tool-desc">{t.desc}</div>
            <span className="tool-stage">{t.stage} · 未交付</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettingsPage() {
  const [theme, setTheme] = useTheme();
  const [info, setInfo] = useState<string>("检查中…");
  useEffect(() => {
    fetch("/api/health")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d) => setInfo(`ds-web ${d.version} 在线 · 数据根 ${d.ds_root}`))
      .catch(() => setInfo("ds-web 离线 —— 用 ds-web.ps1 启动本地服务"));
  }, []);
  const options: { v: Theme; label: string }[] = [
    { v: "auto", label: "跟随系统" },
    { v: "light", label: "浅色" },
    { v: "dark", label: "深色" },
  ];
  return (
    <div className="placeholder">
      <h2>设置</h2>
      <h3>外观</h3>
      <div className="theme-row">
        {options.map((o) => (
          <button
            key={o.v}
            className={theme === o.v ? "on" : ""}
            onClick={() => setTheme(o.v)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <h3>服务</h3>
      <p>{info}</p>
      <p>模型与通道设置在 nanobot WebUI 的 Settings 面板。</p>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState<ModuleKey>(fromHash);
  useTheme(); // 首屏即应用主题(设置页里的是同一份 localStorage 状态)

  useEffect(() => {
    const onHash = () => setActive(fromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="wordmark">
          OpenDesign<span className="wordmark-sub">工作台</span>
        </div>
        <ul>
          {MODULES.map((m) => (
            <li key={m.key}>
              <a
                href={`#/${m.key}`}
                title={m.hint}
                className={active === m.key ? "active" : ""}
                aria-current={active === m.key ? "page" : undefined}
              >
                <Icon name={m.key} />
                <span className="nav-label">{m.label}</span>
              </a>
            </li>
          ))}
        </ul>
        <div className="sidebar-footer">
          <a
            href={`#/${SETTINGS.key}`}
            title={SETTINGS.hint}
            className={active === SETTINGS.key ? "active" : ""}
            aria-current={active === SETTINGS.key ? "page" : undefined}
          >
            <Icon name={SETTINGS.key} />
            <span className="nav-label">{SETTINGS.label}</span>
          </a>
        </div>
      </nav>
      <main className="main">
        {active === "chat" && <ChatPage />}
        {active === "todos" && <TodoPage />}
        {active === "calendar" && (
          <Placeholder
            title="日历"
            lines={["项目排期、量房/交付节点与重要提醒,P2 交付。"]}
          />
        )}
        {active === "toolbox" && <ToolboxPage />}
        {active === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}
