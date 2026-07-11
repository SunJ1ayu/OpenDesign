import { useEffect, useState } from "react";
import type { Ref } from "../api";
import { fetchRefs, refImageUrl } from "../api";

// 伴随列(handoff §3,290px):图片区(参考/效果分段 + 2×2 缩略格)+ 文件区。
// 图片真数据 = /api/projects/<key>/refs + /api/refs/file/ 静态路由;
// refs-index 只索引参考图 ⇒ 「效果」段暂无数据源,给空态(known deviation);
// 文件区:D 盘目录约定未定 → 按稿画壳 + 空态占位(design 决策)。

type Props = { projectKey: string | null };

function thumbLabel(r: Ref): string {
  if (r.note) return r.note;
  const bits = [...r.space.slice(0, 1), ...r.style.slice(0, 1)];
  return bits.join("·") || r.id;
}

export default function CompanionColumn({ projectKey }: Props) {
  const [tab, setTab] = useState<"ref" | "render">("ref");
  const [refs, setRefs] = useState<Ref[] | null>(null);

  useEffect(() => {
    setRefs(null);
    setTab("ref");
    if (!projectKey) {
      setRefs([]);
      return;
    }
    let stale = false;
    fetchRefs(projectKey)
      .then((rs) => {
        if (!stale) setRefs(rs);
      })
      .catch(() => {
        if (!stale) setRefs([]);
      });
    return () => {
      stale = true;
    };
  }, [projectKey]);

  const list = refs ?? [];
  // 2×2 格:>3 张时第 4 格是「+N 图墙」入口;≤3 张全部直接铺
  const showMore = tab === "ref" && list.length > 3;
  const thumbs = tab === "ref" ? (showMore ? list.slice(0, 3) : list) : [];

  return (
    <section className="aside">
      {/* 图片区 */}
      <div className="aside-head">
        <span className="t">图片</span>
        <span className="grow" />
        <div className="seg">
          <button className={`opt${tab === "ref" ? " on" : ""}`} onClick={() => setTab("ref")}>
            参考 {list.length}
          </button>
          <button
            className={`opt${tab === "render" ? " on" : ""}`}
            onClick={() => setTab("render")}
          >
            效果
          </button>
        </div>
      </div>
      {tab === "render" ? (
        <div className="aside-empty">效果图还没有索引来源,后续版本接入。</div>
      ) : refs === null ? (
        <div className="aside-empty">读取中…</div>
      ) : list.length === 0 ? (
        <div className="aside-empty">
          还没有参考图。
          <br />
          在对话里发图并说「登记参考图」,会出现在这里。
        </div>
      ) : (
        <div className="thumb-grid">
          {thumbs.map((r) => (
            <button className="thumb" key={r.id} title={`${r.id} ${thumbLabel(r)}`}>
              <img src={refImageUrl(r.file)} alt={thumbLabel(r)} loading="lazy" />
              <span className="tag">{thumbLabel(r)}</span>
            </button>
          ))}
          {showMore && (
            <button className="thumb more" title="图墙(即将支持)">
              <span className="m">+{list.length - 3} 图墙 →</span>
            </button>
          )}
        </div>
      )}

      {/* 文件区(按稿画壳,空态占位) */}
      <div className="aside-head files">
        <span className="t">项目文件</span>
        <span className="grow" />
      </div>
      <div className="file-search">
        <div className="box">
          <span>⌕</span>
          <span>搜文件名…</span>
        </div>
      </div>
      <div className="file-list">
        <div className="aside-empty" style={{ margin: "4px 8px 0" }}>
          还没有关联项目文件夹。
          <br />
          首次安装后把项目目录(图纸/模型/效果图)关联进来,文件会按类型分组显示。
        </div>
      </div>
    </section>
  );
}
