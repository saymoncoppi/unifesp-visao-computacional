// ===================================================== App state + storage helpers
export const state = { language: "pt-BR", theme: "auto", inspector: "llm" };

export function ls(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
export function lsSet(key, val) { try { localStorage.setItem(key, val); } catch (e) {} }
