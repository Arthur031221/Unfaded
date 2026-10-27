export const LANGUAGES = {
  en: "English",
  "zh-TW": "繁體中文",
  "zh-CN": "简体中文",
  ja: "日本語",
  ko: "한국어",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  "pt-BR": "Português (Brasil)",
};

let dict = {};
let fallback = {};
let current = "en";

export function detect() {
  const saved = localStorage.getItem("unfaded.lang");
  if (saved && LANGUAGES[saved]) return saved;
  for (const raw of navigator.languages || [navigator.language || "en"]) {
    const lower = raw.toLowerCase();
    if (lower === "zh-tw" || lower === "zh-hk" || lower === "zh-hant") return "zh-TW";
    if (lower.startsWith("zh")) return "zh-CN";
    if (lower === "pt-br" || lower.startsWith("pt")) return "pt-BR";
    const short = lower.split("-")[0];
    if (LANGUAGES[short]) return short;
  }
  return "en";
}

async function load(code) {
  const res = await fetch(`locales/${code}.json`);
  if (!res.ok) throw new Error(`locale ${code}`);
  return res.json();
}

export async function setLanguage(code) {
  if (!Object.keys(fallback).length) fallback = await load("en");
  dict = code === "en" ? fallback : await load(code).catch(() => fallback);
  current = code;
  localStorage.setItem("unfaded.lang", code);
  document.documentElement.lang = code;
  apply(document);
}

export function t(key, vars = {}) {
  let text = dict[key] ?? fallback[key] ?? key;
  for (const [name, value] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, value);
  return text;
}

export function has(key) {
  return key in dict || key in fallback;
}

export function apply(root) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
}

export const language = () => current;
