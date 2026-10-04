import type {
  AudienceBody,
  LocalizedText,
  Proposal,
} from "@/lib/contracts.generated";

export type Lang = "en" | "es";
export type Audience = keyof AudienceBody;

/** Pick a language from localized copy, falling back to English when a variant is missing. */
export function localize(text: LocalizedText, lang: Lang): string {
  return text[lang] ?? text.en;
}

export function forFeed(
  copy: AudienceBody,
  audience: Audience,
  lang: Lang,
): string {
  return localize(copy[audience], lang);
}

/** Small labels printed on air, per language. */
export const ON_AIR_TYPE_LABEL: Record<
  Proposal["type"],
  Record<Lang, string>
> = {
  stat_graphic: { en: "Stat", es: "Dato" },
  narrative_line: { en: "Storyline", es: "Historia" },
  tactical_insight: { en: "Tactical insight", es: "Análisis táctico" },
  player_tag: { en: "Player", es: "Jugador" },
  recap_beat: { en: "Recap", es: "Resumen" },
};
