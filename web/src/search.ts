// 搜索面板纯逻辑层(track p4 T4)—— 过滤/高亮切分不掺 DOM,oracle 直测。
// design D2:纯客户端过滤(打开面板时一次性拉取,零新后端表面);
// 大小写不敏感子串匹配;文件/对话两类上游未建,tab 置灰(此处不建 doc 类型)。

export type ChangeDoc = {
  kind: "change";
  project: string;
  cnum: number | null;
  status: string;
  date: string | null;
  space: string | null;
  text: string;
};

export type ImageDoc = {
  kind: "image";
  project: string;
  id: string;
  file: string;
  note: string;
  space: string[];
  style: string[];
};

export type SearchDoc = ChangeDoc | ImageDoc;
export type SearchTab = "all" | "change" | "image";

function hay(d: SearchDoc): string {
  if (d.kind === "change") {
    return [d.text, d.space ?? "", d.cnum !== null ? `C${d.cnum}` : "", d.project]
      .join("\n");
  }
  return [d.note, d.space.join(" "), d.style.join(" "), d.project].join("\n");
}

/** 过滤:query 空 → 空结果(面板初态不倾倒全库);大小写不敏感子串。 */
export function filterDocs(query: string, tab: SearchTab, docs: SearchDoc[]): SearchDoc[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return docs.filter((d) => {
    if (tab === "change" && d.kind !== "change") return false;
    if (tab === "image" && d.kind !== "image") return false;
    return hay(d).toLowerCase().includes(q);
  });
}

/** 高亮切分:text 按 query 命中段切开(大小写不敏感),hit 段渲染 <mark>。
    纯字符串操作 —— 不产 HTML,注入面为零。 */
export function splitHighlight(text: string, query: string): { t: string; hit: boolean }[] {
  const q = query.trim().toLowerCase();
  if (!q) return [{ t: text, hit: false }];
  const out: { t: string; hit: boolean }[] = [];
  const lower = text.toLowerCase();
  let i = 0;
  for (;;) {
    const j = lower.indexOf(q, i);
    if (j < 0) break;
    if (j > i) out.push({ t: text.slice(i, j), hit: false });
    out.push({ t: text.slice(j, j + q.length), hit: true });
    i = j + q.length;
  }
  if (i < text.length) out.push({ t: text.slice(i), hit: false });
  return out.length ? out : [{ t: "", hit: false }];
}
