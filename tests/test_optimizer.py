from aspenops.design import Variable
from aspenops.models import EvaluationResult, RunReport, RunState
from aspenops.optimizer import OptimizationConfig, differential_evolution


def test_differential_evolution_finds_quadratic_minimum() -> None:
    def evaluate(point: dict[str, float]) -> EvaluationResult:
        x = point["x"]
        return EvaluationResult(
            inputs=point,
            outputs={},
            run=RunReport(state=RunState.CONVERGED),
            objective=(x - 2.0) ** 2,
            feasible=True,
        )

    best, history = differential_evolution(
        [Variable("x", -5, 5)],
        evaluate,
        OptimizationConfig(population_size=10, generations=25, seed=42),
    )
    assert abs(best.point["x"] - 2.0) < 0.05
    assert best.result.objective is not None and best.result.objective < 0.003
    assert len(history) == 10 + 25 * 10
