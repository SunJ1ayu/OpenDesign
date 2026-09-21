// 输入框里那颗模型按钮(track opendesign-composer-model-picker)的纯逻辑:菜单里有什么、按钮上写什么、
// 接口回包怎么读。渲染与点击在 ChatPage.tsx;写配置在后端 POST /api/llm/model。
// 判据:tests/test_model_picker.mjs(mp1~mp6)。
//
// 模型是**全局**的(nanobot 底座只有一份 agents.defaults.modelPreset):换了之后首页、项目助手、
// 待办助手下一句都用新模型 —— 所以文案里不说"这个对话"。

export const MODELS_PATH = "/api/llm/models";
export const MODEL_PATH = "/api/llm/model";
export const SWITCH_PROVIDER_LABEL = "换厂商 / 换 key…";
/** 换完之后通知同页其它聊天实例刷新按钮上的字(三个 ChatPage 显示的是同一个全局模型)。 */
export const MODEL_CHANGED_EVENT = "ds-model-changed";

export type ModelOption = { id: string; label: string };
/** 一家厂商一组(track opendesign-per-vendor-keys):后端只列**网关手里有 key** 的厂商。 */
export type ModelGroup = { provider: string; label: string; models: ModelOption[] };
export type ModelsStatus = {
  provider: string | null;
  label: string | null;
  current: string | null;
  models: ModelOption[];
  /** 老后端没有这个字段 ⇒ 按老样子只列当前一家。 */
  groups?: ModelGroup[];
};
export type MenuItem =
  | { kind: "group"; label: string }
  | { kind: "model"; id: string; label: string; active: boolean; provider: string | null }
  | { kind: "sep" }
  | { kind: "switch"; label: string };

function strOrNull(v: unknown): string | null | undefined {
  return v === null ? null : typeof v === "string" ? v : undefined;
}

/** 形状不对一律 null(界面退回网关报的模型名,菜单只剩「换厂商 / 换 key…」)。 */
export function readModelsResponse(status: number, body: unknown): ModelsStatus | null {
  if (status !== 200 || !body || typeof body !== "object") return null;
  const r = body as Record<string, unknown>;
  const provider = strOrNull(r.provider);
  const label = strOrNull(r.label);
  const current = strOrNull(r.current);
  if (provider === undefined || label === undefined || current === undefined) return null;
  const models = readOptions(r.models);
  if (!models) return null;
  if (r.groups === undefined) return { provider, label, current, models };
  if (!Array.isArray(r.groups)) return null;
  const groups: ModelGroup[] = [];
  for (const g of r.groups) {
    const o = (g && typeof g === "object" ? g : {}) as Record<string, unknown>;
    const gm = readOptions(o.models);
    if (typeof o.provider !== "string" || typeof o.label !== "string" || !gm) return null;
    groups.push({ provider: o.provider, label: o.label, models: gm });
  }
  return { provider, label, current, models, groups };
}

function readOptions(v: unknown): ModelOption[] | null {
  if (!Array.isArray(v)) return null;
  const out: ModelOption[] = [];
  for (const m of v) {
    const o = (m && typeof m === "object" ? m : {}) as Record<string, unknown>;
    if (typeof o.id !== "string" || typeof o.label !== "string") return null;
    out.push({ id: o.id, label: o.label });
  }
  return out;
}

export function modelMenuItems(status: ModelsStatus | null): MenuItem[] {
  const tail: MenuItem = { kind: "switch", label: SWITCH_PROVIDER_LABEL };
  if (!status) return [tail];
  // 多厂商:每家一组。打勾要**厂商和模型都对上**(pv3:两家可能有同名模型,不许靠名字判断选中)
  const groups = (status.groups ?? []).filter((g) => g.models.length > 0);
  if (groups.length > 0) {
    const items: MenuItem[] = [];
    for (const g of groups) {
      items.push({ kind: "group", label: g.label });
      for (const m of g.models) {
        items.push({ kind: "model", id: m.id, label: m.label, provider: g.provider,
                     active: g.provider === status.provider && m.id === status.current });
      }
    }
    return [...items, { kind: "sep" }, tail];
  }
  if (status.models.length === 0) return [tail];
  return [
    { kind: "group", label: `${status.label ?? status.provider ?? ""} · 当前这把 key` },
    // 当前模型不在目录里 ⇒ 没有哪行打勾(mp4:不许谎称选中了某一个)
    ...status.models.map((m): MenuItem => (
      { kind: "model", id: m.id, label: m.label, provider: status.provider,
        active: m.id === status.current })),
    { kind: "sep" },
    tail,
  ];
}

/** 点了某一行要 POST 给 /api/llm/model 的东西:**点哪一行就带哪一家**(pv2),后端不必按名字猜。 */
export function modelSelectBody(item: { id: string; provider: string | null }): { model: string; provider?: string } {
  return item.provider ? { model: item.id, provider: item.provider } : { model: item.id };
}

export function modelChipLabel(status: ModelsStatus | null, gatewayModel: string | undefined): string {
  return status?.current || gatewayModel || "选择模型";
}
