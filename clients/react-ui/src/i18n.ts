/**
 * Translations for the UI chrome `ModelPicker` and `AskExternallyButton`
 * render — labels, buttons, hints, aria-labels. Provider names (e.g.
 * "Google Gemini") and their `infoText`/`infoUrl` come from
 * `modeldispatcher-browser-agent`'s registry and stay in English in every
 * locale, the same way the ai-glossary page keeps "Gemini"/"GPT"/"Claude"
 * untranslated: they're product names and provider-hosted external links,
 * not UI copy.
 */

export type Locale = "en" | "fr" | "he";

export const RTL_LOCALES: readonly Locale[] = ["he"];

export interface ModelPickerStrings {
  intro: string;
  emptyState: string;
  modelLabel: string;
  urlLabel: (providerName: string) => string;
  apiKeyLabel: (providerName: string, count: number) => string;
  addKey: string;
  addAnotherKey: string;
  removeProviderLabel: (providerName: string) => string;
  removeKeyLabel: (providerName: string) => string;
  chooseProviderPlaceholder: string;
  chooseProviderAriaLabel: string;
  freeSuffix: string;
  addProviderButton: string;
  favoriteGroupAriaLabel: string;
  favoriteLead: string;
  favoriteNone: string;
  favoriteHint: string;
  glossaryLinkText: string;
}

export interface AskExternallyStrings {
  askButton: (providerName: string) => string;
  openedPrefix: (providerName: string) => string;
  openedWithQuestion: string;
  copiedToClipboard: string;
}

export interface NoProviderStrings {
  lead: string;
  openSettings: string;
  noFavoriteHint: string;
  orDivider: string;
}

export interface ConversationIntroStrings {
  text: string;
}

export interface Strings {
  picker: ModelPickerStrings;
  askExternally: AskExternallyStrings;
  noProvider: NoProviderStrings;
  conversationIntro: ConversationIntroStrings;
}

export const STRINGS: Record<Locale, Strings> = {
  en: {
    picker: {
      intro:
        "Add one or more providers below — they're tried in order, with automatic fallback if one runs out or fails.",
      emptyState: "No providers added yet — add one below to get started.",
      modelLabel: "Model",
      urlLabel: (name) => `${name} URL`,
      apiKeyLabel: (name, count) => `${name} API key${count > 1 ? "s" : ""}`,
      addKey: "+ Add a key",
      addAnotherKey: "+ Add another key",
      removeProviderLabel: (name) => `Remove ${name}`,
      removeKeyLabel: (name) => `Remove this ${name} key`,
      chooseProviderPlaceholder: "Choose a provider…",
      chooseProviderAriaLabel: "Choose a provider to add",
      freeSuffix: " (free)",
      addProviderButton: "+ Add provider",
      favoriteGroupAriaLabel: "Favorite free AI app",
      favoriteLead: "Or save a favorite free AI app for later:",
      favoriteNone: "None",
      favoriteHint: "Just a saved preference — picking one here never opens anything.",
      glossaryLinkText: "New to AI agents? What's a prompt, model, or API key?",
    },
    askExternally: {
      askButton: (name) => `Ask ${name}`,
      openedPrefix: (name) => `Opened ${name}`,
      openedWithQuestion: " with your question filled in",
      copiedToClipboard: " — also copied to your clipboard.",
    },
    noProvider: {
      lead: "You haven't set up an AI provider yet.",
      openSettings: "Open AI settings",
      noFavoriteHint: "Or save a favorite free AI app in Settings to skip API keys entirely.",
      orDivider: "or",
    },
    conversationIntro: {
      text: "You're chatting with AI — replies can be wrong, so double-check anything important.",
    },
  },
  fr: {
    picker: {
      intro:
        "Ajoutez un ou plusieurs fournisseurs ci-dessous — ils sont essayés dans l'ordre, avec un repli automatique si l'un est épuisé ou échoue.",
      emptyState: "Aucun fournisseur ajouté pour l'instant — ajoutez-en un ci-dessous pour commencer.",
      modelLabel: "Modèle",
      urlLabel: (name) => `URL ${name}`,
      apiKeyLabel: (name, count) => `Clé${count > 1 ? "s" : ""} API ${name}`,
      addKey: "+ Ajouter une clé",
      addAnotherKey: "+ Ajouter une autre clé",
      removeProviderLabel: (name) => `Supprimer ${name}`,
      removeKeyLabel: (name) => `Supprimer cette clé ${name}`,
      chooseProviderPlaceholder: "Choisissez un fournisseur…",
      chooseProviderAriaLabel: "Choisir un fournisseur à ajouter",
      freeSuffix: " (gratuit)",
      addProviderButton: "+ Ajouter un fournisseur",
      favoriteGroupAriaLabel: "Application IA gratuite favorite",
      favoriteLead: "Ou enregistrez une application IA gratuite favorite pour plus tard :",
      favoriteNone: "Aucune",
      favoriteHint: "Juste une préférence enregistrée — en choisir une ici n'ouvre jamais rien.",
      glossaryLinkText: "Nouveau dans les agents IA ? Qu'est-ce qu'un prompt, un modèle ou une clé API ?",
    },
    askExternally: {
      askButton: (name) => `Demander à ${name}`,
      openedPrefix: (name) => `${name} ouvert`,
      openedWithQuestion: " avec votre question déjà remplie",
      copiedToClipboard: " — également copiée dans le presse-papiers.",
    },
    noProvider: {
      lead: "Vous n'avez pas encore configuré de fournisseur IA.",
      openSettings: "Ouvrir les réglages IA",
      noFavoriteHint:
        "Ou enregistrez une application IA gratuite favorite dans les réglages pour éviter les clés API.",
      orDivider: "ou",
    },
    conversationIntro: {
      text: "Vous discutez avec une IA — les réponses peuvent être fausses, vérifiez tout ce qui compte.",
    },
  },
  he: {
    picker: {
      intro: "הוסיפו ספק אחד או יותר למטה — הם ינוסו לפי הסדר, עם מעבר אוטומטי לחלופה אם אחד נכשל או נגמר.",
      emptyState: "עדיין לא נוספו ספקים — הוסיפו אחד למטה כדי להתחיל.",
      modelLabel: "מודל",
      urlLabel: (name) => `כתובת URL של ${name}`,
      apiKeyLabel: (name, count) => `מפתח${count > 1 ? "ות" : ""} API של ${name}`,
      addKey: "+ הוספת מפתח",
      addAnotherKey: "+ הוספת מפתח נוסף",
      removeProviderLabel: (name) => `הסרת ${name}`,
      removeKeyLabel: (name) => `הסרת מפתח ${name} זה`,
      chooseProviderPlaceholder: "בחרו ספק…",
      chooseProviderAriaLabel: "בחירת ספק להוספה",
      freeSuffix: " (חינם)",
      addProviderButton: "+ הוספת ספק",
      favoriteGroupAriaLabel: "אפליקציית AI חינמית מועדפת",
      favoriteLead: "או שמרו אפליקציית AI חינמית מועדפת לשימוש מאוחר יותר:",
      favoriteNone: "ללא",
      favoriteHint: "רק העדפה שמורה — בחירה כאן לעולם לא פותחת שום דבר.",
      glossaryLinkText: "חדשים בעולם סוכני ה-AI? מה זה פרומפט, מודל או מפתח API?",
    },
    askExternally: {
      askButton: (name) => `שאלו את ${name}`,
      openedPrefix: (name) => `${name} נפתח`,
      openedWithQuestion: " עם השאלה שלכם כבר ממולאת",
      copiedToClipboard: " — היא גם הועתקה ללוח.",
    },
    noProvider: {
      lead: "עדיין לא הגדרתם ספק AI.",
      openSettings: "פתיחת הגדרות AI",
      noFavoriteHint: "או שמרו אפליקציית AI חינמית מועדפת בהגדרות כדי לדלג לגמרי על מפתחות API.",
      orDivider: "או",
    },
    conversationIntro: {
      text: "אתם משוחחים עם AI — התשובות עלולות להיות שגויות, בדקו כל דבר חשוב בעצמכם.",
    },
  },
};

export function resolveStrings(locale: Locale): Strings {
  return STRINGS[locale];
}

export function dirFor(locale: Locale): "rtl" | "ltr" {
  return RTL_LOCALES.includes(locale) ? "rtl" : "ltr";
}
