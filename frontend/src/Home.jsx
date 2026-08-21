import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { getNextSession, getLastRace, getStandingsByOpenF1Key } from "./api";
import DriverBadge from "./DriverBadge";
import TeamPill from "./TeamPill";
import "./App.css";

const POLL_INTERVAL_MS = 30000;

function useCountdown(targetDateStr) {
  const [timeLeft, setTimeLeft] = useState(null);

  useEffect(() => {
    if (!targetDateStr) return;
    const target = new Date(targetDateStr).getTime();

    const tick = () => {
      const now = Date.now();
      const diff = target - now;
      if (diff <= 0) {
        setTimeLeft({ live: true });
        return;
      }
      setTimeLeft({
        live: false,
        days: Math.floor(diff / (1000 * 60 * 60 * 24)),
        hours: Math.floor((diff / (1000 * 60 * 60)) % 24),
        minutes: Math.floor((diff / (1000 * 60)) % 60),
        seconds: Math.floor((diff / 1000) % 60),
      });
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [targetDateStr]);

  return timeLeft;
}

function CountdownBlock({ countdown }) {
  const segments = [
    ["Days", countdown.days],
    ["Hrs", countdown.hours],
    ["Min", countdown.minutes],
    ["Sec", countdown.seconds],
  ];

  return (
    <div className="countdown-block">
      {segments.map(([label, value]) => (
        <div key={label} className="countdown-segment">
          <span className="value">{String(value).padStart(2, "0")}</span>
          <span className="label">{label}</span>
        </div>
      ))}
    </div>
  );
}

function Home() {
  const [nextSession, setNextSession] = useState(null);
  const [lastRace, setLastRace] = useState(null);
  const [lastRaceResults, setLastRaceResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchHomeData = useCallback(async () => {
    try {
      const [session, race] = await Promise.all([
        getNextSession(),
        getLastRace(),
      ]);

      setNextSession(session);
      setLastRace(race);

      if (race) {
        const results = await getStandingsByOpenF1Key(race.session_key);
        setLastRaceResults(results);
      }

      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHomeData();
    const interval = setInterval(fetchHomeData, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchHomeData]);

  const countdown = useCountdown(nextSession?.date_start);
  const isLive = countdown?.live;

  return (
    <div style={{ minHeight: `calc(100svh - var(--nav-height))`, color: "var(--text)" }}>
      {/* --- Hero section --- */}
      <section className="hero-section px-8 md:px-16 pt-10 pb-16">
        <div className="bg-checker" />
        <div className="max-w-4xl mx-auto relative" style={{ zIndex: 1 }}>
          <span className="status-badge">
            <span className="live-dot" />
            2026 Season Live
          </span>

          <h1 className="hero-headline">
            Every Millisecond.
            <span className="gradient-line">Every Insight.</span>
          </h1>

          <p className="max-w-md" style={{ color: "var(--text-dim)", fontSize: 17, lineHeight: 1.6 }}>
            A live timing dashboard for Formula 1 — track sectors, gaps, tyre strategy,
            and championship standings, built from real race data.
          </p>
        </div>
      </section>

      {loading ? (
        <p style={{ color: "var(--text-dim)" }} className="max-w-4xl mx-auto px-8">Loading…</p>
      ) : error ? (
        <p style={{ color: "var(--accent)" }} className="max-w-4xl mx-auto px-8">{error}</p>
      ) : (
        <div className="max-w-4xl mx-auto px-8 md:px-16 pb-16 space-y-6">

          {/* --- Next session: full-width, single-block countdown --- */}
          <section className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="eyebrow">{isLive ? "Happening now" : "Next session"}</div>
              {nextSession && <span className="session-tag">{nextSession.session_name}</span>}
            </div>

            {nextSession ? (
              <div className="flex flex-wrap items-center justify-between gap-6">
                <div>
                  <p className="text-3xl md:text-4xl font-bold mb-1" style={{ fontFamily: "var(--font-display)" }}>
                    {nextSession.country_name}
                  </p>
                  <p className="font-mono text-sm" style={{ color: "var(--text-dim)" }}>
                    {nextSession.circuit_short_name}
                  </p>
                </div>

                {!isLive && countdown && <CountdownBlock countdown={countdown} />}

                {isLive && (
                  <Link
                    to="/live"
                    className="inline-block px-6 py-3 font-semibold"
                    style={{ background: "var(--accent)", color: "#fff", borderRadius: "2px" }}
                  >
                    Go to live dashboard →
                  </Link>
                )}
              </div>
            ) : (
              <p style={{ color: "var(--text-faint)" }}>No upcoming session found.</p>
            )}
          </section>

          {/* --- Full last-race results, scrollable --- */}
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between p-6 pb-4">
              <div className="eyebrow">
                Last race — full results
                {lastRace && <span style={{ color: "var(--text-faint)" }}> · {lastRace.country_name}</span>}
              </div>
              <span className="font-mono text-xs" style={{ color: "var(--text-faint)" }}>
                {lastRaceResults.length} finishers
              </span>
            </div>

            {lastRaceResults.length > 0 ? (
              <div className="results-scroll">
                <table className="timing-table">
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>Pos</th>
                      <th style={{ width: 60 }}>#</th>
                      <th>Driver</th>
                      <th>Team</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lastRaceResults.map((r) => (
                      <tr
                        key={r.driver_number}
                        className="stripe-row"
                        style={{ "--stripe": r.team_colour ? `#${r.team_colour}` : undefined }}
                      >
                        <td className="mono-num" style={{ color: r.position === 1 ? "var(--live-green)" : "var(--text-faint)" }}>
                          {r.position}
                        </td>
                        <td><DriverBadge number={r.driver_number} colour={r.team_colour} size="sm" /></td>
                        <td className="font-medium">{r.full_name}</td>
                        <td><TeamPill fullName={r.full_name} colour={r.team_colour} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-6 pb-6" style={{ color: "var(--text-faint)" }}>No results available.</p>
            )}
          </section>

        </div>
      )}
    </div>
  );
}

export default Home;