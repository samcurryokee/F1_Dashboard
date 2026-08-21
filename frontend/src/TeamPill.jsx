// Derives a 3-letter code from a driver's full name as a stand-in for
// OpenF1's real name_acronym field, which isn't in the current schema.
export function driverCode(fullName) {
  if (!fullName) return "???";
  const parts = fullName.trim().split(" ");
  const lastName = parts[parts.length - 1];
  return lastName.slice(0, 3).toUpperCase();
}

// Picks black or white text based on background luminance so the pill
// stays readable across every team color.
function contrastText(hex) {
  if (!hex) return "#0b0c0f";
  const clean = hex.replace("#", "");
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#0b0c0f" : "#ffffff";
}

function TeamPill({ fullName, colour }) {
  const bg = colour ? `#${colour}` : "var(--stripe-fallback)";
  const textColor = colour ? contrastText(colour) : "#fff";
  return (
    <span className="team-pill" style={{ background: bg, color: textColor }}>
      {driverCode(fullName)}
    </span>
  );
}

export default TeamPill;