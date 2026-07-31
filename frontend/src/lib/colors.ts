export interface ColorTheme {
  dot: string;
  chip: string;
  selected: string;
  ring: string;
}

const THEMES: Record<string, ColorTheme> = {
  amber: {
    dot: "bg-amber-500",
    chip: "bg-amber-500/10 text-amber-300 border-amber-700/40",
    selected: "border-amber-600 bg-amber-500/10",
    ring: "ring-amber-600/50",
  },
  rose: {
    dot: "bg-rose-500",
    chip: "bg-rose-500/10 text-rose-300 border-rose-700/40",
    selected: "border-rose-600 bg-rose-500/10",
    ring: "ring-rose-600/50",
  },
  violet: {
    dot: "bg-violet-500",
    chip: "bg-violet-500/10 text-violet-300 border-violet-700/40",
    selected: "border-violet-600 bg-violet-500/10",
    ring: "ring-violet-600/50",
  },
  emerald: {
    dot: "bg-emerald-500",
    chip: "bg-emerald-500/10 text-emerald-300 border-emerald-700/40",
    selected: "border-emerald-600 bg-emerald-500/10",
    ring: "ring-emerald-600/50",
  },
  teal: {
    dot: "bg-teal-500",
    chip: "bg-teal-500/10 text-teal-300 border-teal-700/40",
    selected: "border-teal-600 bg-teal-500/10",
    ring: "ring-teal-600/50",
  },
};

const FALLBACK = THEMES.teal;

export function personaTheme(personaId: string, color?: string): ColorTheme {
  if (personaId === "tutor") return THEMES.teal;
  return THEMES[color ?? ""] ?? FALLBACK;
}
