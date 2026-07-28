import { useState } from "react";
import ChatPage from "../chat/ChatPage";
import InboxCard from "./InboxCard";
import FolderVisibilityCard from "./FolderVisibilityCard";
import type { ChatSession } from "../chat/connection";

// 聊天列(handoff §4,340px):头部(项目助手 / ≡ / » 收起)+ ChatPage 真身。
// 收起(design 窄窗策略:稿上有 » 按钮)= 收成 36px 竖条,« 展开。
// P3 keep-mounted 同规矩:收起也走 CSS 隐藏,不卸载 ChatPage(卸载=丢对话)。

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
  /** 体检卡存完后刷新项目列表(藏/显直接改变左侧列表)。 */
  onVisibilitySaved?: () => void;
};

export default function ChatColumn({
  session, prefill, dispatch, onConnected, onTurnEnd,
  resume, onChatId, onAttachFailed, firstSendPrefix, projectLabel, onNewChat,
  dataEpoch = 0, inboxActive = false, onVisibilitySaved,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className={`chatcol${collapsed ? " collapsed" : ""}`}>
      {/* ⓪ 收件箱(-p2,用户提的:放项目助手上面,款式对齐左列)。
          原先刻意让它在收起态也留着(理由:它不属于聊天,不该跟着聊天消失)——
          **2026-07-27 真机截图推翻了这条**:36px 竖条里它只能被压成一字一行的竖排、
          还顶出视口右缘,"留着"等于留一片看不懂的残字。改成随收起一起 CSS 隐藏
          (app.css `.chatcol.collapsed > .inbox-card`),仍然不卸载。
          代价记账:收起期间看不到收件箱提示;collapsed 不持久化,刷新即回展开态。 */}
      <InboxCard dataEpoch={dataEpoch} active={inboxActive} />
      {/* 工作区体检卡(track opendesign-workspace-health T8):被程序猜掉的
          文件夹的**纠正入口**。同 InboxCard:没事整卡不渲染。 */}
      <FolderVisibilityCard dataEpoch={dataEpoch} active={inboxActive}
                            onSaved={onVisibilitySaved} />
      {collapsed ? (
        <div className="chat-rail">
          <button className="icon-btn" title="展开项目助手" onClick={() => setCollapsed(false)}>
            «
          </button>
        </div>
      ) : (
        <div className="chatcol-head">
          <span className="t">项目助手</span>
          <span className="grow" />
          {onNewChat && (
            <button className="icon-btn" title="新对话(这个项目重新开一条)" onClick={onNewChat}>
              +
            </button>
          )}
          <button className="icon-btn" title="收起" onClick={() => setCollapsed(true)}>
            »
          </button>
        </div>
      )}
      <div className={`chatcol-body${collapsed ? " route-hidden" : ""}`}>
        <ChatPage
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
        />
      </div>
    </section>
  );
}
