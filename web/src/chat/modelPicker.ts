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
export type ModelsStatus = {
  provider: string | null;
  label: string | null;
  current: string | null;
  models: ModelOption[];
};
export type MenuItem =
  | { kind: "group"; label: string }
  | { kind: "model"; id: string; label: string; active: boolean }
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
  if (!Array.isArray(r.models)) return null;
  const models: ModelOption[] = [];
  for (const m of r.models) {
    const o = (m && typeof m === "object" ? m : {}) as Record<string, unknown>;
    if (typeof o.id !== "string" || typeof o.label !== "string") return null;
    models.push({ id: o.id, label: o.label });
  }
  return { provider, label, current, models };
}

export function modelMenuItems(status: ModelsStatus | null): MenuItem[] {
  const tail: MenuItem = { kind: "switch", label: SWITCH_PROVIDER_LABEL };
  if (!status || status.models.length === 0) return [tail];
  return [
    { kind: "group", label: `${status.label ?? status.provider ?? ""} · 当前这把 key` },
    // 当前模型不在目录里 ⇒ 没有哪行打勾(mp4:不许谎称选中了某一个)
    ...status.models.map((m): MenuItem => (
      { kind: "model", id: m.id, label: m.label, active: m.id === status.current })),
    { kind: "sep" },
    tail,
  ];
}

export function modelChipLabel(status: ModelsStatus | null, gatewayModel: string | undefined): string {
  return status?.current || gatewayModel || "选择模型";
}
