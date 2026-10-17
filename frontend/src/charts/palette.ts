// Categorical slots in fixed order (validated for colour-blind separation on the light surface).
// Colour follows the entity, never its rank: assign by the entity's position in its watchlist.
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

// Sentiment is polarity, so it uses the diverging pair with a gray midpoint.
export const SENTIMENT = { positive: "#2a78d6", neutral: "#c3c2b7", negative: "#e34948" } as const;

export const GRID = "#e7e5e0";
export const AXIS_TEXT = "#52514e";

export function seriesColor(index: number): string {
  return SERIES[index % SERIES.length];
}
