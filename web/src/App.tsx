import { useState } from "react";
import { EquityPage } from "./features/equity/EquityPage";
import { SolutionsPage } from "./features/solutions/SolutionsPage";
import { SolverPage } from "./features/solver/SolverPage";
import { t } from "./i18n/pt-BR";

export function App() {
  const [tab, setTab] = useState<"solver" | "solutions" | "equity">("solver");
  // a aba Equity monta na primeira visita e depois fica montada (preserva cálculo e entradas)
  const [equityVisited, setEquityVisited] = useState(false);
  return (
    <>
      <nav className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "solver"} onClick={() => setTab("solver")}>
          {t.tabs.solver}
        </button>
        <button type="button" role="tab" aria-selected={tab === "solutions"} onClick={() => setTab("solutions")}>
          {t.tabs.solutions}
        </button>
        <button type="button" role="tab" aria-selected={tab === "equity"} onClick={() => {
            setTab("equity");
            setEquityVisited(true);
          }}>
          {t.tabs.equity}
        </button>
      </nav>
      <div hidden={tab !== "solver"}>
        <SolverPage />
      </div>
      {tab === "solutions" && <SolutionsPage />}
      {equityVisited && (
        <div hidden={tab !== "equity"}>
          <EquityPage />
        </div>
      )}
    </>
  );
}
