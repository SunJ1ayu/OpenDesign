import { useEffect, useState } from "react";
import TodoPage from "./TodoPage";

// 模块表 = design.md D3 侧栏五项。P0 只有"待办"是真的;占位模块各自说明
// 自己是什么、什么时候来(空屏是行动邀请,不是道歉)。
const MODULES = [
  { key: "todos", label: "待办", hint: "未关闭变更与超期项目" },
  { key: "chat", label: "聊天", hint: "暂在 nanobot WebUI" },
  { key: "images", label: "图片规整", hint: "P3 · 批量统一宽度" },
  { key: "viewer", label: "3D 查看", hint: "P4 · 户型模型" },
  { key: "settings", label: "设置", hint: "服务状态" },
] as const;

type ModuleKey = (typeof MODULES)[number]["key"];

function fromHash(): ModuleKey {
  const h = window.location.hash.replace("#/", "");
  return (MODULES.some((m) => m.key === h) ? h : "todos") as ModuleKey;
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

function Health() {
  const [info, setInfo] = useState<string>("检查中…");
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setInfo(`ds-web ${d.version} 在线 · 数据根 ${d.ds_root}`))
      .catch(() => setInfo("ds-web 离线 —— 用 ds-web.ps1 启动本地服务"));
  }, []);
  return <Placeholder title="设置" lines={[info, "模型与通道设置在 nanobot WebUI 的 Settings 面板。"]} />;
}

export default function App() {
  const [active, setActive] = useState<ModuleKey>(fromHash);

  useEffect(() => {
    const onHash = () => setActive(fromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="wordmark">
          <span className="wordmark-open">Open</span>Design
          <span className="wordmark-sub">工作台</span>
        </div>
        <ul>
          {MODULES.map((m) => (
            <li key={m.key}>
              <a
                href={`#/${m.key}`}
                className={active === m.key ? "active" : ""}
                aria-current={active === m.key ? "page" : undefined}
              >
                <span className="nav-label">{m.label}</span>
                <span className="nav-hint">{m.hint}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <main className="main">
        {active === "todos" && <TodoPage />}
        {active === "chat" && (
          <div className="placeholder">
            <h2>聊天</h2>
            <p>聊天暂时还在 nanobot 自带 WebUI 里,收进工作台是 P1 的活。</p>
            <p className="placeholder-action">
              <a href="http://127.0.0.1:8765/" target="_blank" rel="noreferrer">
                打开 nanobot WebUI（127.0.0.1:8765）
              </a>
            </p>
          </div>
        )}
        {active === "images" && (
          <Placeholder
            title="图片规整"
            lines={[
              "把不同长宽的图片批量统一宽度/分辨率,方便排版导出 PDF。",
              "P3 交付;输出永远是新目录副本,不动原图。",
            ]}
          />
        )}
        {active === "viewer" && (
          <Placeholder
            title="3D 查看"
            lines={["户型 CAD→3D 模型查看,P4 在工作台内重写。"]}
          />
        )}
        {active === "settings" && <Health />}
      </main>
    </div>
  );
}
