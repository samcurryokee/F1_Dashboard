import { useState, useEffect, useCallback } from "react";
import { getSessions, getStandings, getLapsDetailed, getCurrentTyres } from "./api";
import { tireColor, tireLabel } from "./tireCompounds";
import DriverBadge from "./DriverBadge";
import "./App.css";

const REFRESH_INTERVAL_MS = 5000;

function PitInIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1v8M3.5 6L7 9.5 10.5 6" stroke="var(--accent)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="1.5" y="10.5" width="11" height="2" rx="0.5" fill="var(--accent)" />
    </svg>
  );
}

function PitOutIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 9.5v-8M3.5 4.5L7 1l3.5 3.5" stroke="var(--text-dim)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="1.5" y="10.5" width="11" height="2" rx="0.5" fill="var(--text-dim)" />
    </svg>
  );
}

function TireBadge({ compound }) {
  const color = tireColor(compound);
  const label = tireLabel(compound);
  return (
    <span
      title={compound || "Unknown"}
      className="inline-flex items-center justify-center font-mono text-[11px] font-bold"
      style={{
        width: 20,
        height: 20,
        borderRadius: "50%",
        background: color,
        color: color === "#f0f0f0" || color === "#ffd400" ? "#0b0c0f" : "#fff",
        border: "1.5px solid rgba(255,255,255,0.15)",
      }}
    >
      {label}
    </span>
  );
}

function fmtTime(v) {
  return v !== null && v !== undefined ? v.toFixed(3) : "-";
}

function LivePage() {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [activeTab, setActiveTab] = useState("standings");

  const [standings, setStandings] = useState([]);
  const [laps, setLaps] = useState([]);
  const [tyresByDriver, setTyresByDriver] = useState({});

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    getSessions()
      .then((data) => {
        setSessions(data);
        if (data.length > 0) setSelectedSessionId(data[0].id);
      })
      .catch((err) => setError(err.message));
  }, []);

  const refreshData = useCallback(async () => {
    if (selectedSessionId === null) return;
    try {
      const tyres = await getCurrentTyres(selectedSessionId);
      const tyreMap = {};
      tyres.forEach((t) => { tyreMap[t.driver_number] = t; });
      setTyresByDriver(tyreMap);

      if (activeTab === "standings") {
        const data = await getStandings(selectedSessionId);
        setStandings(data);
      } else {
        const data = await getLapsDetailed(selectedSessionId);
        setLaps(data);
      }
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedSessionId, activeTab]);

  useEffect(() => {
    setLoading(true);
    refreshData();
  }, [refreshData]);

  useEffect(() => {
    const interval = setInterval(refreshData, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshData]);

  const selectedSession = sessions.find((s) => s.id === selectedSessionId);

  return (
    <div style={{ minHeight: `calc(100svh - var(--nav-height))`, color: "var(--text)" }} className="px-6 py-8 md:px-10">
      <div className="max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl md:text-4xl font-bold">F1 Live Dashboard</h1>
          {selectedSession && (
            <p className="mt-1 font-mono text-sm" style={{ color: "var(--text-dim)" }}>
              {selectedSession.year} {selectedSession.country_name} — {selectedSession.session_name} ·{" "}
              {selectedSession.circuit_short_name}
            </p>
          )}
        </header>

        <div className="flex flex-wrap items-center gap-4 mb-6">
          {sessions.length > 0 && (
            <select
              className="select-minimal"
              value={selectedSessionId ?? ""}
              onChange={(e) => setSelectedSessionId(Number(e.target.value))}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.year} {s.country_name} — {s.session_name}
                </option>
              ))}
            </select>
          )}

          <div className="segmented">
            <button
              className={activeTab === "standings" ? "active" : ""}
              onClick={() => setActiveTab("standings")}
            >
              <span>Standings</span>
            </button>
            <button
              className={activeTab === "laps" ? "active" : ""}
              onClick={() => setActiveTab("laps")}
            >
              <span>Laps</span>
            </button>
          </div>

          {lastUpdated && (
            <span
              className="flex items-center gap-2 font-mono text-xs ml-auto"
              style={{ color: "var(--text-faint)" }}
            >
              <span className="live-dot" />
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>

        {error && (
          <div
            className="mb-4 p-3 text-sm"
            style={{
              background: "var(--accent-dim)",
              borderLeft: "3px solid var(--accent)",
              color: "var(--text)",
              borderRadius: "2px",
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: "var(--text-dim)" }}>Loading…</p>
        ) : activeTab === "standings" ? (
          <StandingsTable rows={standings} tyresByDriver={tyresByDriver} />
        ) : (
          <LapsTable rows={laps} />
        )}

        <div className="flex items-center gap-4 mt-4 font-mono text-xs" style={{ color: "var(--text-faint)" }}>
          <span className="flex items-center gap-1.5"><PitInIcon /> Pit in</span>
          <span className="flex items-center gap-1.5"><PitOutIcon /> Pit out</span>
          <span className="flex items-center gap-1.5">
            {["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"].map((c) => (
              <span key={c} className="flex items-center gap-1 mr-2">
                <TireBadge compound={c} /> {c[0]}
              </span>
            ))}
          </span>
        </div>
      </div>
    </div>
  );
}

function StandingsTable({ rows, tyresByDriver }) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--text-dim)" }}>No standings data available yet.</p>;
  }

  return (
    <div className="card overflow-hidden">
      <table className="timing-table">
        <thead>
          <tr>
            <th style={{ width: 40 }}>Pos</th>
            <th style={{ width: 40 }}>#</th>
            <th>Driver</th>
            <th>Team</th>
            <th style={{ width: 60 }}>Tyre</th>
            <th>Gap to leader</th>
            <th>Interval</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const tyre = tyresByDriver[row.driver_number];
            return (
              <tr
                key={row.driver_number}
                className="stripe-row"
                style={{ "--stripe": row.team_colour ? `#${row.team_colour}` : undefined }}
              >
                <td className="mono-num" style={{ color: "var(--text-faint)" }}>{row.position ?? "-"}</td>
                <td><DriverBadge number={row.driver_number} colour={row.team_colour} /></td>
                <td className="font-medium">{row.full_name}</td>
                <td style={{ color: "var(--text-dim)" }}>{row.team_name}</td>
                <td>{tyre ? <TireBadge compound={tyre.compound} /> : <span style={{ color: "var(--text-faint)" }}>-</span>}</td>
                <td className="mono-num text-sm">
                  {row.gap_to_leader !== null ? `+${row.gap_to_leader.toFixed(3)}s` : "-"}
                </td>
                <td className="mono-num text-sm">
                  {row.interval !== null ? `+${row.interval.toFixed(3)}s` : "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LapsTable({ rows }) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--text-dim)" }}>No lap data available yet.</p>;
  }

  return (
    <div className="card max-h-[70vh] overflow-y-auto">
      <table className="timing-table">
        <thead>
          <tr>
            <th>Driver #</th>
            <th>Lap</th>
            <th>S1</th>
            <th>S2</th>
            <th>S3</th>
            <th>Lap time</th>
            <th style={{ width: 70 }}>Pit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.driver_number}-${row.lap_number}-${i}`} className="stripe-row">
              <td className="mono-num">{row.driver_number}</td>
              <td className="mono-num">{row.lap_number}</td>
              <td className="mono-num text-sm" style={{ color: "var(--text-dim)" }}>{fmtTime(row.duration_sector_1)}</td>
              <td className="mono-num text-sm" style={{ color: "var(--text-dim)" }}>{fmtTime(row.duration_sector_2)}</td>
              <td className="mono-num text-sm" style={{ color: "var(--text-dim)" }}>{fmtTime(row.duration_sector_3)}</td>
              <td className="mono-num text-sm font-medium">
                {row.lap_duration !== null ? `${row.lap_duration.toFixed(3)}s` : "-"}
              </td>
              <td>
                <div className="flex items-center gap-1.5">
                  {row.is_pit_out_lap && <PitOutIcon />}
                  {row.is_pit_in_lap && <PitInIcon />}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default LivePage;