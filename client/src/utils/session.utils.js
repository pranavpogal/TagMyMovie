const sessionStorageKey = "tagmymovie.sessionId";

const createSessionId = () => {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const getSessionId = () => {
  let sessionId = sessionStorage.getItem(sessionStorageKey);
  if (!sessionId) {
    sessionId = createSessionId();
    sessionStorage.setItem(sessionStorageKey, sessionId);
  }
  return sessionId;
};

const sessionUtils = { getSessionId };

export default sessionUtils;
