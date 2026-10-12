import { useState } from "react";
import { SolutionsPage } from "./features/solutions/SolutionsPage";
import { SolverPage } from "./features/solver/SolverPage";
import { t } from "./i18n/pt-BR";

export function App() {
  const [tab, setTab] = useState<"solver" | "solutions">("solver");
  return (
    <>
      <nav className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "solver"} onClick={() => setTab("solver")}>
          {t.tabs.solver}
        </button>
        <button type="button" role="tab" aria-selected={tab === "solutions"} onClick={() => setTab("solutions")}>
          {t.tabs.solutions}
        </button>
      </nav>
      <div hidden={tab !== "solver"}>
        <SolverPage />
      </div>
      {tab === "solutions" && <SolutionsPage />}
    </>
  );
}
