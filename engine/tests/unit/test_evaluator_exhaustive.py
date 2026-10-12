"""T008 — teste exaustivo do avaliador de 5 cartas (fonte: combinatória padrão, REFERENCES.md)."""

import numpy as np
import pytest
from numba import njit

from gto_engine.evaluator import hand_category
from gto_engine.evaluator.kernels import eval5

ESPERADO = {
    8: 40,  # straight flush (inclui royal)
    7: 624,  # quadra
    6: 3_744,  # full house
    5: 5_108,  # flush
    4: 10_200,  # sequência
    3: 54_912,  # trinca
    2: 123_552,  # dois pares
    1: 1_098_240,  # par
    0: 1_302_540,  # carta alta
}


@njit(cache=True)
def _todas_as_mao_de_5() -> np.ndarray:
    out = np.empty(2_598_960, dtype=np.int32)
    k = 0
    for a in range(52):
        for b in range(a + 1, 52):
            for c in range(b + 1, 52):
                for d in range(c + 1, 52):
                    for e in range(d + 1, 52):
                        out[k] = eval5(a, b, c, d, e)
                        k += 1
    return out


@pytest.mark.slow
def test_2598960_maos_7462_classes_e_contagens() -> None:
    forcas = _todas_as_mao_de_5()
    assert forcas.shape[0] == 2_598_960
    assert np.unique(forcas).shape[0] == 7_462
    cats = np.array([hand_category(int(s)) for s in np.unique(forcas)])
    del cats
    contagem = {cat: 0 for cat in range(9)}
    valores, freq = np.unique(forcas, return_counts=True)
    for v, f in zip(valores, freq, strict=True):
        contagem[hand_category(int(v))] += int(f)
    assert contagem == ESPERADO
