import type { Language } from "./types";

export interface Strings {
  tagline: string;
  newConversation: string;
  discuss: string;
  study: string;
  chooseThinkers: (n: number, max: number) => string;
  roundtableSuffix: string;
  tutorName: string;
  tutorBlurb: string;
  lockedHint: string;
  history: string;
  emptyHistory: string;
  browseLibrary: string;
  welcomeDialogue: string;
  welcomeRoundtable: string;
  welcomeStudy: string;
  welcomeDiscussHint: string;
  tutorGreeting: string;
  placeholderAsk: string;
  placeholderRoundtable: string;
  placeholderStudy: string;
  send: string;
  thinking: string;
  composerHint: string;
  moderatorNote: string;
  backendError: string;
  traceBoard: string;
  tracesTitle: string;
  tracesSubtitle: (n: number) => string;
  tracesEmpty: string;
  allSessions: string;
  backToConversations: string;
  traceRetrieval: string;
  traceReply: string;
  traceCritic: string;
  traceTranslatedQuery: string;
  traceSupported: string;
  traceOverreach: string;
  traceNoVerdict: string;
  traceCacheHit: string;
  traceErrorLabel: string;
  traceStatusAborted: string;
  backToLibrary: string;
  loadingText: string;
  textLoadError: string;
  askAboutSelection: string;
  selectionTooLong: string;
  dockLeft: string;
  dockRight: string;
  readTab: string;
  chatTab: string;
  summoning: (name: string) => string;
  summoningHint: string;
  summonFailed: string;
  retrySummon: string;
  placeholderReading: (name: string) => string;
}

const STRINGS: Record<Language, Strings> = {
  en: {
    tagline: "Conversations with the dead greats, grounded in their books.",
    newConversation: "+ New conversation",
    discuss: "discuss",
    study: "study",
    chooseThinkers: (n: number, max: number) =>
      `Choose up to ${max} thinkers (${n}/${max})`,
    roundtableSuffix: " — roundtable",
    tutorName: "The Tutor",
    tutorBlurb:
      "Explanations, Socratic questions, and quizzes grounded in the library.",
    lockedHint:
      "Mode, language, and speakers are set per conversation. Start a new one to change them.",
    history: "History",
    emptyHistory: "No conversations yet.",
    browseLibrary: "→ Browse the library",
    welcomeDialogue: "Begin the dialogue",
    welcomeRoundtable: "Convene a roundtable",
    welcomeStudy: "Study with the Tutor",
    welcomeDiscussHint:
      "Ask about virtue, dreams, power, the Tao — every answer is drawn from the primary texts in the library.",
    tutorGreeting:
      "Welcome. Tell me what you are studying — a thinker, a movement, a period — and I will explain it, question you on it, or quiz you, drawing on the library's texts.",
    placeholderAsk: "Ask your question…",
    placeholderRoundtable: "Pose a question to the roundtable…",
    placeholderStudy: "Ask for an explanation, a Socratic dialogue, or a quiz…",
    send: "Send",
    thinking: "Thinking…",
    composerHint:
      "Enter to send · Shift+Enter for a new line · Personas speak from retrieved passages, but they are still interpretations.",
    moderatorNote: "Moderator's note",
    backendError: "is the backend running? (uv run uvicorn app.main:app --reload)",
    traceBoard: "→ Trace board",
    tracesTitle: "Trace board",
    tracesSubtitle: (n: number) =>
      `${n} traced queries — every question's journey through retrieval, personas, and the critic.`,
    tracesEmpty: "No traces yet — ask something first.",
    allSessions: "All conversations",
    backToConversations: "← Back to conversations",
    traceRetrieval: "Retrieval",
    traceReply: "Reply",
    traceCritic: "Critic",
    traceTranslatedQuery: "Translated for retrieval",
    traceSupported: "supported",
    traceOverreach: "overreach noted",
    traceNoVerdict: "no verdict",
    traceCacheHit: "cache hit",
    traceErrorLabel: "Error",
    traceStatusAborted: "aborted",
    backToLibrary: "← Back to the library",
    loadingText: "Loading the text…",
    textLoadError: "Could not load the text.",
    askAboutSelection: "Ask about selection",
    selectionTooLong: "Selection too long — highlight a shorter passage",
    dockLeft: "Dock chat to the left",
    dockRight: "Dock chat to the right",
    readTab: "Read",
    chatTab: "Chat",
    summoning: (name: string) => `Summoning ${name}…`,
    summoningHint:
      "Forging a new persona from the author's works and reference sources — this can take up to a minute.",
    summonFailed: "Could not summon the author — reading only.",
    retrySummon: "Try again",
    placeholderReading: (name: string) => `Ask ${name} about the text…`,
  },
  zh: {
    tagline: "与逝去的伟大思想家对话，根植于他们的著作。",
    newConversation: "+ 新对话",
    discuss: "对话",
    study: "学习",
    chooseThinkers: (n: number, max: number) =>
      `最多选择 ${max} 位思想家（${n}/${max}）`,
    roundtableSuffix: " — 圆桌讨论",
    tutorName: "导师",
    tutorBlurb: "基于馆藏文本的讲解、苏格拉底式提问与测验。",
    lockedHint: "模式、语言与对话者在每个对话中固定。开启新对话即可更改。",
    history: "历史记录",
    emptyHistory: "暂无对话。",
    browseLibrary: "→ 浏览书库",
    welcomeDialogue: "开始对话",
    welcomeRoundtable: "召开圆桌讨论",
    welcomeStudy: "与导师一同学习",
    welcomeDiscussHint: "探讨美德、梦境、权力、道——每个回答都取自书库中的原典。",
    tutorGreeting:
      "欢迎。告诉我你在研读的主题——一位思想家、一场运动、一个时代——我会为你讲解、提问，或用测验检验你，一切都基于书库中的文本。",
    placeholderAsk: "提出你的问题…",
    placeholderRoundtable: "向圆桌提问…",
    placeholderStudy: "请导师讲解、进行苏格拉底式对话，或来一组测验…",
    send: "发送",
    thinking: "思考中…",
    composerHint:
      "Enter 发送 · Shift+Enter 换行 · 角色的发言基于检索到的原文段落，但仍属于一种诠释。",
    moderatorNote: "主持人按语",
    backendError: "后端是否在运行？(uv run uvicorn app.main:app --reload)",
    traceBoard: "→ 追踪面板",
    tracesTitle: "追踪面板",
    tracesSubtitle: (n: number) =>
      `${n} 条已追踪的查询——每个问题在检索、角色与评审中的完整旅程。`,
    tracesEmpty: "暂无追踪记录——先去提个问题吧。",
    allSessions: "全部对话",
    backToConversations: "← 返回对话",
    traceRetrieval: "检索",
    traceReply: "回复",
    traceCritic: "评审",
    traceTranslatedQuery: "检索用翻译",
    traceSupported: "有据可查",
    traceOverreach: "超出原文",
    traceNoVerdict: "无结论",
    traceCacheHit: "缓存命中",
    traceErrorLabel: "错误",
    traceStatusAborted: "已中止",
    backToLibrary: "← 返回书库",
    loadingText: "正在载入文本…",
    textLoadError: "无法载入文本。",
    askAboutSelection: "询问所选段落",
    selectionTooLong: "所选内容过长——请选取更短的段落",
    dockLeft: "对话栏置于左侧",
    dockRight: "对话栏置于右侧",
    readTab: "阅读",
    chatTab: "对话",
    summoning: (name: string) => `正在召唤${name}…`,
    summoningHint: "正在根据作者的著作与参考资料塑造新角色——可能需要一分钟。",
    summonFailed: "无法召唤作者——仅供阅读。",
    retrySummon: "重试",
    placeholderReading: (name: string) => `就文本向${name}提问…`,
  },
};

export function strings(language: Language | string | undefined): Strings {
  return STRINGS[language === "zh" ? "zh" : "en"];
}
