// Standard F1 broadcast tire-compound color coding.
export const TIRE_COLORS = {
  SOFT: "#e10600",
  MEDIUM: "#ffd400",
  HARD: "#f0f0f0",
  INTERMEDIATE: "#3dae2b",
  WET: "#0067ad",
  UNKNOWN: "#5c6070",
};

export const TIRE_LABELS = {
  SOFT: "S",
  MEDIUM: "M",
  HARD: "H",
  INTERMEDIATE: "I",
  WET: "W",
  UNKNOWN: "?",
};

export function tireColor(compound) {
  return TIRE_COLORS[compound?.toUpperCase()] || TIRE_COLORS.UNKNOWN;
}

export function tireLabel(compound) {
  return TIRE_LABELS[compound?.toUpperCase()] || TIRE_LABELS.UNKNOWN;
}