# Contrato público do motor — `gto_engine` (feature 002)

API Python que a camada `gto_api` (e os testes) consomem. Nada fora destes módulos é público.
O motor **não importa** `fastapi`, `pydantic`, `sqlalchemy` nem nada de `gto_api`
(regra `TID251` do ruff, Princípio III). Tipos são dataclasses `frozen=True` + arrays NumPy.

```python
# gto_engine.game
def build_tree(spot: Spot, config: TreeConfig) -> GameTree: ...
def estimate_tree(spot: Spot, config: TreeConfig) -> TreeEstimate: ...   # sem alocar arrays
def default_tree_config() -> TreeConfig: ...
def input_hash(spot: Spot, config: TreeConfig, params: SolveParams) -> str: ...  # SHA-256 hex

# gto_engine.solver
class SolveControl(Protocol):
    def should_stop(self) -> bool: ...          # parar ou cancelar solicitado
    def wait_if_paused(self) -> None: ...       # bloqueia enquanto pausado

ProgressSink = Callable[[Progress], None]

def solve(
    tree: GameTree,
    params: SolveParams,
    control: SolveControl = NEVER_STOP,
    on_progress: ProgressSink = ignore,
) -> SolveResult: ...  # treino + finalização (estratégia média, EV, equity); Solution + stop_reason

def exploitability(tree: GameTree, strategy: Strategy) -> float: ...   # % do pote (R6)

# gto_engine.analysis — só leitura e agregação (≤ 200 ms, research R15)
def node_view(tree: GameTree, solution: Solution, path: NodePath) -> NodeView: ...

# gto_engine.io
def save_solution_dir(solution: Solution, directory: Path) -> int: ...      # .npy sem compressão; retorna bytes
def open_solution_dir(directory: Path) -> Solution: ...                     # arrays via mmap (somente leitura)
def export_npz(directory: Path, target: Path, control: SolveControl = NEVER_STOP,
               on_progress: Callable[[float], None] = ignore) -> None: ...          # escrita em fatias
def import_npz(source: Path, directory: Path, control: SolveControl = NEVER_STOP,
               on_progress: Callable[[float], None] = ignore) -> SolutionMeta: ...   # leitura em fatias
# cancelamento via control: levanta Cancelled e remove saídas parciais
# erros: SolutionFormatError (arquivo_invalido) / IncompatibleVersionError (versao_incompativel)

# gto_engine.toy_games  (validação, Princípio I)
def kuhn_tree() -> GameTree: ...
def leduc_tree() -> GameTree: ...
```

## Garantias

| Garantia | Verificação |
|----------|-------------|
| Mesmas entradas + `params` + nº de iterações ⇒ `Solution.strategy` idêntica byte a byte (mesma plataforma) | teste de determinismo |
| `save_solution_dir` → `export_npz` → `import_npz` → `open_solution_dir` ⇒ arrays e meta idênticos; `node_view` idêntico | teste ida e volta |
| `node_view` ≤ 200 ms no maior flop aceito (4 GiB) | benchmark |
| `exploitability` ≥ 0 e = 0 (± 1e-9) para equilíbrio exato de jogos triviais | teste unitário |
| `estimate_tree` dentro de ±15% dos bytes alocados | teste de estimativa |
| `should_stop()` consultado a cada bloco de ≤ ~200 ms no treino, na finalização, em `export_npz` e em `import_npz` | teste de latência de parada e de cancelamento |
| Erros de entrada levantam `InvalidSpotError` / `InvalidTreeConfigError` com mensagem pt-BR | testes unitários |
