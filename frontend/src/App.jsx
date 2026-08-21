import { Routes, Route, NavLink } from "react-router-dom";
import Home from "./Home";
import LivePage from "./LivePage";
import StandingsPage from "./StandingsPage";
import "./App.css";

function navClass({ isActive }) {
  return `top-nav-link${isActive ? " active" : ""}`;
}

function App() {
  return (
    <>
      <nav className="top-nav">
        <div className="top-nav-inner">
          <div className="flex items-center gap-3">
            <div className="logo-mark" />
            <span className="top-nav-brand">F1 Dashboard</span>
          </div>

          <div className="top-nav-links">
            <NavLink to="/" end className={navClass}>Home</NavLink>
            <NavLink to="/live" className={navClass}>Live Timings</NavLink>
            <NavLink to="/standings" className={navClass}>Standings</NavLink>
          </div>
        </div>
      </nav>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/live" element={<LivePage />} />
          <Route path="/standings" element={<StandingsPage />} />
        </Routes>
      </main>
    </>
  );
}

export default App;