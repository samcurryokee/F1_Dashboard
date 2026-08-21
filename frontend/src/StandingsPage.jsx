import { useState, useEffect } from "react";
import { getDriverChampionship, getConstructorChampionship } from "./api";
import DriverBadge from "./DriverBadge";
import "./App.css";

function StandingsPage() {
  const [activeTab, setActiveTab] = useState("drivers");
  const [driverStandings, setDriverStandings] = useState([]);
  const [constructorStandings, setConstructorStandings] = useState([]);
  const [year] = useState(2026);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const load =
      activeTab === "drivers"
        ? getDriverChampionship(year)
        : getConstructorChampionship(year);

    load
      .then((data) => {
        if (activeTab === "drivers") setDriverStandings(data.standings);
        else setConstructorStandings(data.standings);
      })
      .catch((err) => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [activeTab, year]);

  return (
    <div style={{ minHeight: `calc(100svh - var(--nav-height))`, color: "var(--text)" }} className="px-6 py-8 md:px-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl md:text-4xl font-bold">{year} Championship</h1>
          <p className="mt-1 font-mono text-sm" style={{ color: "var(--text-dim)" }}>
            Computed from every completed race result seeded this season
          </p>
        </header>

        <div className="flex items-center gap-4 mb-6">
          <div className="segmented">
            <button
              className={activeTab === "drivers" ? "active" : ""}
              onClick={() => setActiveTab("drivers")}
            >
              <span>Drivers</span>
            </button>
            <button
              className={activeTab === "constructors" ? "active" : ""}
              onClick={() => setActiveTab("constructors")}
            >
              <span>Constructors</span>
            </button>
          </div>
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
        ) : activeTab === "drivers" ? (
          <DriversTable rows={driverStandings} />
        ) : (
          <ConstructorsTable rows={constructorStandings} />
        )}
      </div>
    </div>
  );
}

function DriversTable({ rows }) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--text-dim)" }}>No standings available yet.</p>;
  }

  return (
    <div className="card overflow-hidden">
      <table className="timing-table">
        <thead>
          <tr>
            <th style={{ width: 48 }}>Pos</th>
            <th style={{ width: 40 }}>#</th>
            <th>Driver</th>
            <th>Team</th>
            <th>Wins</th>
            <th>Podiums</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.driver_number}
              className="stripe-row"
              style={{ "--stripe": row.team_colour ? `#${row.team_colour}` : undefined }}
            >
              <td className="mono-num" style={{ color: "var(--text-faint)" }}>{row.position}</td>
              <td><DriverBadge number={row.driver_number} colour={row.team_colour} size="sm" /></td>
              <td className="font-medium">{row.full_name}</td>
              <td style={{ color: "var(--text-dim)" }}>{row.team_name}</td>
              <td className="mono-num text-sm">{row.wins}</td>
              <td className="mono-num text-sm">{row.podiums}</td>
              <td className="mono-num font-semibold">{row.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConstructorsTable({ rows }) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--text-dim)" }}>No standings available yet.</p>;
  }

  return (
    <div className="card overflow-hidden">
      <table className="timing-table">
        <thead>
          <tr>
            <th style={{ width: 48 }}>Pos</th>
            <th>Team</th>
            <th>Wins</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.team_name}
              className="stripe-row"
              style={{ "--stripe": row.team_colour ? `#${row.team_colour}` : undefined }}
            >
              <td className="mono-num" style={{ color: "var(--text-faint)" }}>{row.position}</td>
              <td className="font-medium">{row.team_name}</td>
              <td className="mono-num text-sm">{row.wins}</td>
              <td className="mono-num font-semibold">{row.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default StandingsPage;