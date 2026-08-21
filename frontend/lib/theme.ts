import type { CSSProperties } from "react";

export type ThemePalette = "pulso" | "ocean" | "creative" | "natural" | "custom";
export type ThemeColors = {
  theme_structure: string;
  theme_action: string;
  theme_wayfinding: string;
  theme_background: string;
  theme_text: string;
};

export const THEME_PRESETS: Record<Exclude<ThemePalette, "custom">, { label: string; colors: ThemeColors }> = {
  pulso: {
    label: "Pulso Comercial",
    colors: { theme_structure: "#020530", theme_action: "#BD1D59", theme_wayfinding: "#007F96", theme_background: "#FFFFFF", theme_text: "#020530" },
  },
  ocean: {
    label: "Océano",
    colors: { theme_structure: "#063B5C", theme_action: "#A72F59", theme_wayfinding: "#006D77", theme_background: "#F4FBFC", theme_text: "#082F3A" },
  },
  creative: {
    label: "Creativa",
    colors: { theme_structure: "#3B1E54", theme_action: "#A91F5B", theme_wayfinding: "#006F78", theme_background: "#FFF8FC", theme_text: "#2B1538" },
  },
  natural: {
    label: "Natural",
    colors: { theme_structure: "#183B32", theme_action: "#9C2F4A", theme_wayfinding: "#2D6A4F", theme_background: "#FAFCF7", theme_text: "#183B32" },
  },
};

export function resolveThemeVariables(theme: ThemeColors) {
  return {
    "--ink": theme.theme_text,
    "--blue": theme.theme_structure,
    "--cyan": theme.theme_wayfinding,
    "--cyan-action": theme.theme_wayfinding,
    "--magenta": theme.theme_action,
    "--magenta-action": theme.theme_action,
    "--magenta-dark": `color-mix(in srgb, ${theme.theme_action}, #000 15%)`,
    "--surface": theme.theme_background,
    "--surface-elevated": `color-mix(in srgb, ${theme.theme_background}, #fff 18%)`,
    "--surface-cold": `color-mix(in srgb, ${theme.theme_background} 94%, ${theme.theme_wayfinding} 6%)`,
    "--surface-cyan": `color-mix(in srgb, ${theme.theme_background} 90%, ${theme.theme_wayfinding} 10%)`,
    "--muted": `color-mix(in srgb, ${theme.theme_text} 72%, ${theme.theme_background})`,
    "--line": `color-mix(in srgb, ${theme.theme_structure} 17%, ${theme.theme_background})`,
  } as CSSProperties & Record<`--${string}`, string>;
}
