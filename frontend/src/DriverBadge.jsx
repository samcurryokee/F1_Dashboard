function DriverBadge({ number, colour, size = "md" }) {
  const dims = size === "sm" ? { width: 24, height: 18, fontSize: 11 } : { width: 28, height: 22, fontSize: 12 };
  return (
    <span
      className="inline-flex items-center justify-center font-mono font-semibold"
      style={{
        width: dims.width,
        height: dims.height,
        fontSize: dims.fontSize,
        background: colour ? `#${colour}` : "var(--stripe-fallback)",
        color: "#0b0c0f",
        borderRadius: "2px",
        flexShrink: 0,
      }}
    >
      {number}
    </span>
  );
}

export default DriverBadge;