import ChatPage from "../chat/ChatPage";
import InboxCard from "./InboxCard";
import type { ChatSession } from "../chat/connection";

// 聊天列:头部(项目助手 / + 新对话)+ ChatPage 真身。住在项目页右侧面板的「项目助手」标签里
// (SidePane,照 ZCode Side Pane)。以前自带的「» 收起成 36px 竖条」取消了 —— 收起整块右侧面板
// 由主区右上角的开关负责,一处收起就够。
// P3 keep-mounted 同规矩:面板收起 / 切到别的标签都走 CSS 隐藏,不卸载 ChatPage(卸载=丢对话)。

type Props = {
  session: ChatSession;
  prefill?: { text: string; nonce: number };
  dispatch?: { text: string; nonce: number }; // connect-ux:程序化发送透传
  onConnected?: () => void;
  onTurnEnd?: () => void;
  // project-thread:每项目一条工作对话(App 派生/记账,本组件只透传)
  resume?: { sessionKey: string; chatId: string; nonce: number } | null;
  onChatId?: (chatId: string) => void;
  onAttachFailed?: () => void;
  firstSendPrefix?: string;
  projectLabel?: string;   // -p2:聊天存图起名用(纯透传)
  dataEpoch?: number;      // -p2:收件箱卡片搬到本列顶部,沿用同一刷新节拍
  inboxActive?: boolean;   // -p2:路由门(仅工作区路由拉收件箱数据)
  onNewChat?: () => void; // 清当前项目映射+强制新会话
  /** 换模型弹框底行「管理模型」→ 设置页模型设置(纯透传给 ChatPage)。 */
  onManageModels?: (provider: string | null) => void;
  /** 这条对话冒出了业主同意卡:外层要把右侧面板打开、切到「项目助手」(卡藏着 = 助手在等、业主看不见)。 */
  onConsentPending?: () => void;
};

export default function ChatColumn({
  session, prefill, dispatch, onConnected, onTurnEnd,
  resume, onChatId, onAttachFailed, firstSendPrefix, projectLabel, onNewChat,
  dataEpoch = 0, inboxActive = false, onManageModels, onConsentPending,
}: Props) {
  return (
    <section className="chatcol">
      {/* ⓪ 收件箱(-p2,用户提的:放项目助手上面,款式对齐左列)。
          原先刻意让它在收起态也留着(理由:它不属于聊天,不该跟着聊天消失)——
          **2026-07-27 真机截图推翻了这条**:36px 竖条里它只能被压成一字一行的竖排、
          还顶出视口右缘,"留着"等于留一片看不懂的残字。改成随收起一起 CSS 隐藏
          (app.css `.chatcol.collapsed > .inbox-card`),仍然不卸载。
          代价记账:收起期间看不到收件箱提示;collapsed 不持久化,刷新即回展开态。 */}
      {/* 业主同意卡原来排在这里(收件箱上面)。track opendesign-consent-dock 照 ZCode
          挪进了 ChatPage 的输入卡正上方 —— 首页聊天也要有,而且助手的工具现在会停下来等它,
          卡必须出现在业主眼睛正看着的地方。别在这里再放一张(会出两张)。 */}
      <InboxCard dataEpoch={dataEpoch} active={inboxActive} />
      {/* 工作区体检卡曾经在这里(T8)。**2026-07-28 用户拍板挪进「设置」** ——
          他自己说的用法是"偶尔校一次",常驻一张低频卡片是占地方。
          现在由 App 渲染在设置浮层里,本列不再出面(挪走就挪干净,别两处都有)。 */}
      <div className="chatcol-head">
        <span className="t">项目助手</span>
        <span className="grow" />
        {onNewChat && (
          <button className="icon-btn" title="新对话(这个项目重新开一条)" onClick={onNewChat}>
            +
          </button>
        )}
      </div>
      <div className="chatcol-body">
        <ChatPage
          slot="workspace"
          session={session}
          prefill={prefill}
          dispatch={dispatch}
          onConnected={onConnected}
          onTurnEnd={onTurnEnd}
          resume={resume}
          onChatId={onChatId}
          onAttachFailed={onAttachFailed}
          firstSendPrefix={firstSendPrefix}
          projectLabel={projectLabel}
          onManageModels={onManageModels}
          consentActive={inboxActive}
          onConsentPending={onConsentPending}
        />
      </div>
    </section>
  );
}
