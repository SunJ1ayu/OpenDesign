// 输入卡右下角「换模型」弹框,照 ZCode `packages/ui/src/ModelConfigSelect.tsx`(track opendesign-zcode-model-settings):
// 每家一行(当前那家 ✓ + ›)→ 移上去 / 点一下向右弹出这家的模型(当前 ✓)→ 底部粘性「管理模型」进设置页。
// 菜单内容由 modelPicker.modelMenuTree 算(判据 mp / pv);这里只管摆放与指针。
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { MenuModel, MenuTree } from "./modelPicker";

type Props = {
  tree: MenuTree;
  busy: boolean;
  error: string;
  onPick: (m: MenuModel) => void;
  onManage: (provider: string | null) => void;
};

// Radix 子菜单有「指针宽限」:鼠标从厂商行斜着移向子菜单时会擦过别的行,不能一擦就收(QA A23)。
// 这里用一口延时代替它的三角区:移到别的行 200ms 后才换/收,期间进了子菜单就取消。
const GRACE_MS = 200;

export function CheckIcon() {
  return (
    <svg className="mm-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="mm-icon chev" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 18 6-6-6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function ModelMenu({ tree, busy, error, onPick, onManage }: Props) {
  const [open, setOpen] = useState<string | null>(null);   // 展开的是哪一家(provider ?? "")
  const [subTop, setSubTop] = useState(0);
  const [flip, setFlip] = useState(false);                 // 右边放不下 ⇒ 子菜单翻到左边(Radix 的碰撞处理)
  const timer = useRef<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLDivElement>(null);
  const rows = useRef(new Map<string, HTMLButtonElement>());

  const cancel = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };
  useEffect(() => cancel, []);
  const openNow = (key: string) => {
    cancel();
    const row = rows.current.get(key);
    if (row) setSubTop(row.offsetTop - 5);
    setOpen(key);
  };
  const later = (fn: () => void) => {
    cancel();
    timer.current = window.setTimeout(() => {
      timer.current = null;
      fn();
    }, GRACE_MS);
  };

  // 碰撞处理(Radix 的 avoidCollisions 同义):右边放不下 ⇒ 翻到左边;下面放不下 ⇒ 往上挪(菜单向上弹,按钮贴着窗口底)
  useLayoutEffect(() => {
    const row = open === null ? null : rows.current.get(open);
    if (!row || !menuRef.current || !subRef.current) return;
    const menu = menuRef.current.getBoundingClientRect();
    const subH = subRef.current.offsetHeight;
    setFlip(menu.right + 4 + subRef.current.offsetWidth > window.innerWidth - 8);
    const want = row.offsetTop - 5;
    const overflow = menu.top + want + subH - (window.innerHeight - 8);
    setSubTop(Math.max(want - Math.max(0, overflow), 8 - menu.top));
  }, [open]);

  const vendor = open === null ? null : tree.vendors.find((v) => (v.provider ?? "") === open) ?? null;

  return (
    <div className="model-menu" data-ui="chat-model-menu" role="menu" ref={menuRef}>
      {tree.vendors.map((v) => {
        const key = v.provider ?? "";
        return (
          <button
            key={key}
            ref={(el) => {
              if (el) rows.current.set(key, el);
              else rows.current.delete(key);
            }}
            className={`item vendor${open === key ? " open" : ""}`}
            role="menuitem"
            aria-haspopup="menu"
            aria-expanded={open === key}
            data-ui="chat-model-vendor"
            data-provider={v.provider ?? undefined}
            data-selected={v.active ? "true" : undefined}
            onMouseEnter={() => {
              if (open === null) openNow(key);
              else if (open === key) cancel();
              else later(() => openNow(key));
            }}
            onClick={() => openNow(key)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") {
                e.preventDefault();
                openNow(key);
                window.setTimeout(() => subRef.current?.querySelector<HTMLButtonElement>("button")?.focus(), 0);
              }
            }}
          >
            <span className="name" title={v.label}>{v.label}</span>
            {v.active && <span className="check"><CheckIcon /></span>}
            <ChevronRightIcon />
          </button>
        );
      })}
      {vendor && (
        <div
          className={`model-sub${flip ? " flip" : ""}`}
          role="menu"
          ref={subRef}
          data-ui="chat-model-sub"
          data-provider={vendor.provider ?? undefined}
          style={{ top: subTop }}
          onMouseEnter={cancel}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") {
              e.preventDefault();
              rows.current.get(open ?? "")?.focus();
              setOpen(null);
            }
          }}
        >
          {vendor.models.map((m) => (
            <button
              key={m.id}
              className={`item${m.active ? " active" : ""}`}
              role="menuitemradio"
              aria-checked={m.active}
              data-model-id={m.id}
              data-provider={m.provider ?? undefined}
              disabled={busy}
              onClick={() => onPick(m)}
            >
              <span className="name" title={m.label}>{m.label}</span>
              <span className="check">{m.active ? <CheckIcon /> : null}</span>
            </button>
          ))}
        </div>
      )}
      <div className="foot">
        {tree.vendors.length > 0 && <div className="sep" />}
        <button
          className="item"
          role="menuitem"
          data-ui="chat-model-manage"
          onMouseEnter={() => later(() => setOpen(null))}
          onClick={() => onManage(tree.manage.provider)}
        >
          <span className="name">{tree.manage.label}</span>
        </button>
      </div>
      {error && <div className="err" data-ui="chat-model-error">{error}</div>}
    </div>
  );
}
