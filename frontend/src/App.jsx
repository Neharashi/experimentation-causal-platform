import { useState } from "react";
import PowerCalculator from "./components/PowerCalculator.jsx";
import Analyze from "./components/Analyze.jsx";
import Guide from "./components/Guide.jsx";

const TABS = [
  ["analyze", "Analyze"],
  ["design", "Design a test"],
  ["guide", "Method guide"],
];

export default function App() {
  const [tab, setTab] = useState("analyze");
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">Δ</span>
          <div>
            <h1>Experimentation &amp; Causal Inference</h1>
            <p>Design tests, analyze them correctly, estimate effects when you can't randomize.</p>
          </div>
        </div>
        <nav>
          {TABS.map(([key, label]) => (
            <button key={key} className={tab === key ? "tab active" : "tab"} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === "analyze" && <Analyze />}
        {tab === "design" && <PowerCalculator />}
        {tab === "guide" && <Guide />}
      </main>
      <footer>FastAPI · statsmodels · PyMC · DoWhy · EconML · React</footer>
    </div>
  );
}
