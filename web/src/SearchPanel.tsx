import { useEffect, useMemo, useRef, useState } from "react";
import { fetchChanges, fetchProjects, fetchRefs, refImageUrl } from "./api";
import {
  filterDocs,
  splitHighlight,
  type SearchDoc,
  type SearchTab,
} from "./search";

// 5a 搜索命令面板(track p4 T4,handoff §7):⌘K 浮层,不是页面。
// design D2:打开时一次性拉全部项目的 变更+图片索引,纯客户端过滤(零新后端
// 表面);文件/对话两类上游未建 → tab 置灰。过滤/高亮在 ./search.ts(oracle 直测)。

type Props = {
  open: boolean;
  onClose: () => void;
  onOpenChange: (project: string, cnum: number | null) => void;
  onOpenProject: (project: string) => void;
};

const TABS: { key: SearchTab | "file" | "chat"; label: string; disabled?: boolean }[] = [
  { key: "all", label: "全部" },
  { key: "change", label: "变更" },
  { key: "file", label: "文件", disabled: true },
  { key: "image", label: "图片" },
  { key: "chat", label: "对话", disabled: true },
];
const LIVE_TABS: SearchTab[] = ["all", "change", "image"];

function Hi({ text, q }: { text: string; q: string }) {
  return (
    <>
      {splitHighlight(text, q).map((s, i) =>
        s.hit ? <mark key={i}>{s.t}</mark> : <span key={i}>{s.t}</span>,
      )}
    </>
  );
}

export default function SearchPanel({ open, onClose, onOpenChange, onOpenProject }: Props) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<SearchTab>("all");
  const [docs, setDocs] = useState<SearchDoc[] | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // 打开 → 复位 + 聚焦。⚠️必须与下面的加载 effect 分开:若共用依赖 [open, docs],
  // 索引到位那刻 effect 重跑会把用户已敲的 query 清空(e2e 抓到的真 bug)。
  useEffect(() => {
    if (!open) {
      setDocs(null); // 关闭即弃索引:会话内新记的变更下次打开能搜到(panel p4 submimo 指出)
      return;
    }
    setQuery("");
    setSel(0);
    setTab("all");
    inputRef.current?.focus();
  }, [open]);

  // 每次打开拉一次索引(打开期间缓存,关闭失效)
  useEffect(() => {
    if (!open || docs !== null) return;
    let stale = false;
    (async () => {
      try {
        const ps = await fetchProjects();
        const per = await Promise.all(
          ps.map(async (p) => {
            const [changes, refs] = await Promise.all([
              fetchChanges(p.key).catch(() => []),
              fetchRefs(p.key).catch(() => []),
            ]);
            const cds: SearchDoc[] = changes.map((c) => ({
              kind: "change" as const,
              project: p.key,
              cnum: c.cnum,
              status: c.status,
              date: c.date,
              space: c.space,
              text: c.text,
            }));
            const ids: SearchDoc[] = refs.map((r) => ({
              kind: "image" as const,
              project: p.key,
              id: r.id,
              file: r.file,
              note: r.note,
              space: r.space,
              style: r.style,
            }));
            return [...cds, ...ids];
          }),
        );
        if (!stale) setDocs(per.flat());
      } catch (e) {
        if (!stale) setLoadErr(`索引读取失败(${(e as Error).message})`);
      }
    })();
    return () => {
      stale = true;
    };
  }, [open, docs]);

  const results = useMemo(
    () => (docs ? filterDocs(query, tab, docs) : []),
    [docs, query, tab],
  );
  const selClamped = Math.min(sel, Math.max(0, results.length - 1));

  const pick = (d: SearchDoc) => {
    onClose();
    if (d.kind === "change") onOpenChange(d.project, d.cnum);
    else onOpenProject(d.project);
  };

  // 键盘:↑↓ 选择 / ↵ 打开 / esc 关 / tab 切分类(仅可用 tab 轮换)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSel((s) => Math.min(s + 1, Math.max(0, results.length - 1)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSel((s) => Math.max(s - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (results[selClamped]) pick(results[selClamped]);
      } else if (e.key === "Tab") {
        e.preventDefault();
        setTab((t) => LIVE_TABS[(LIVE_TABS.indexOf(t) + 1) % LIVE_TABS.length]);
        setSel(0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!open) return null;

  const changes = results.filter((d) => d.kind === "change");
  const images = results.filter((d) => d.kind === "image");
  let idx = -1; // 全局行号(跨组连续,键盘选中用)

  const rowCls = () => {
    idx += 1;
    return `sp-row${idx === selClamped ? " sel" : ""}`;
  };

  return (
    <div className="sp-mask" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sp-panel" role="dialog" aria-label="搜索">
        <div className="sp-input">
          <span className="ico">⌕</span>
          <input
            ref={inputRef}
            value={query}
            placeholder="搜变更、图片…"
            onChange={(e) => {
              setQuery(e.target.value);
              setSel(0);
            }}
          />
          <span className="esc-tag">esc</span>
        </div>
        <div className="sp-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              disabled={t.disabled}
              className={`pill${tab === t.key ? " on" : ""}${t.disabled ? " off" : ""}`}
              title={t.disabled ? "上游还没建,先置灰" : undefined}
              onClick={() => {
                if (!t.disabled) {
                  setTab(t.key as SearchTab);
                  setSel(0);
                }
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="sp-results">
          {loadErr && <div className="sp-hint error-note">{loadErr}</div>}
          {!loadErr && docs === null && <div className="sp-hint muted">索引读取中…</div>}
          {docs !== null && query.trim() === "" && (
            <div className="sp-hint muted">输入关键词,精确查找变更与图片(不经过 AI)</div>
          )}
          {docs !== null && query.trim() !== "" && results.length === 0 && (
            <div className="sp-hint muted">没有匹配的结果</div>
          )}
          {changes.length > 0 && (
            <div className="sp-group">
              <div className="g-title">变更记录</div>
              {changes.map((d) => (
                <button
                  className={rowCls()}
                  key={`c:${d.project}:${d.cnum}:${d.text}`}
                  onClick={() => pick(d)}
                >
                  <span className="cnum">{d.cnum !== null ? `C${d.cnum}` : "—"}</span>
                  <span className="txt"><Hi text={d.text} q={query} /></span>
                  <span className="meta">
                    {d.project}
                    {d.space ? ` · ${d.space}` : ""}
                  </span>
                  <span className="enter">↵</span>
                </button>
              ))}
            </div>
          )}
          {images.length > 0 && (
            <div className="sp-group">
              <div className="g-title">图片</div>
              {images.map((d) => (
                <button
                  className={rowCls()}
                  key={`i:${d.project}:${d.id}`}
                  onClick={() => pick(d)}
                >
                  <img className="thumb" src={refImageUrl(d.file)} alt="" loading="lazy" />
                  <span className="txt"><Hi text={d.note || d.file} q={query} /></span>
                  <span className="meta">{d.project}</span>
                  <span className="enter">↵</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="sp-foot">
          <span>↑↓ 选择</span>
          <span>↵ 打开</span>
          <span>tab 切分类</span>
          <span className="grow" />
          <span>{query.trim() ? `${results.length} 个结果` : ""}</span>
        </div>
      </div>
    </div>
  );
}
