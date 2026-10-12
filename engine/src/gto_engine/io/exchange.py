"""Exportação/importação de soluções como .npz comprimido, em fatias (research R4/R12).

O .npz é um zip ZIP_DEFLATED com um membro `<nome>.npy` por array e `meta.json.npy` (bytes do
JSON); continua legível por `numpy.load(..., allow_pickle=False)`. Escrita e leitura são feitas
em blocos de `CHUNK_BYTES`, consultando o controle entre blocos; ao cancelar, nenhum arquivo ou
diretório parcial é deixado.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.lib import format as npformat

from gto_engine.game.tree import TREE_ARRAYS
from gto_engine.io.solution_dir import (
    ARRAYS,
    FORMAT_VERSION,
    IncompatibleVersionError,
    SolutionFormatError,
    SolutionMeta,
    read_meta,
)
from gto_engine.solver.finalize import SolveCancelled

Cancelled = SolveCancelled
CHUNK_BYTES = int(os.environ.get("GTO_EXCHANGE_CHUNK_BYTES", 8 * 1024 * 1024))
META_MEMBER = "meta.json.npy"


def _stop(control: Any) -> bool:
    return control is not None and bool(control.should_stop())


def _ignore(_: float) -> None:
    return None


def export_npz(
    directory: Path,
    target: Path,
    control: Any = None,
    on_progress: Callable[[float], None] = _ignore,
) -> None:
    directory, target = Path(directory), Path(target)
    meta = read_meta(directory)
    arrays = {n: np.load(directory / f"{n}.npy", mmap_mode="r", allow_pickle=False) for n in ARRAYS}
    if (directory / "tree.json").exists():  # árvore gravada (T101) viaja junto
        arrays["tree.json"] = np.frombuffer((directory / "tree.json").read_bytes(), dtype=np.uint8)
        for n in TREE_ARRAYS:
            arrays[f"tree_{n}"] = np.load(
                directory / f"tree_{n}.npy", mmap_mode="r", allow_pickle=False
            )
    meta_bytes = np.frombuffer(
        json.dumps(asdict(meta), ensure_ascii=False).encode(), dtype=np.uint8
    )
    total = sum(a.nbytes for a in arrays.values()) + meta_bytes.nbytes or 1
    done = 0
    part = target.with_name(target.name + ".part")
    on_progress(0.0)
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for name, arr in [("meta.json", meta_bytes), *arrays.items()]:
                flat = np.ascontiguousarray(arr).reshape(-1)
                with zf.open(f"{name}.npy", "w", force_zip64=True) as fp:
                    npformat.write_array_header_1_0(
                        fp, npformat.header_data_from_array_1_0(np.asarray(arr))
                    )
                    step = max(1, CHUNK_BYTES // max(1, flat.itemsize))
                    for i in range(0, flat.shape[0], step):
                        if _stop(control):
                            raise Cancelled()
                        chunk = flat[i : i + step]
                        fp.write(chunk.tobytes())
                        done += chunk.nbytes
                        on_progress(min(0.999, done / total))
        os.replace(part, target)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    on_progress(1.0)


def _read_header(fp: Any) -> tuple[tuple[int, ...], bool, np.dtype[Any]]:
    version = npformat.read_magic(fp)
    if version == (1, 0):
        shape, fortran, dtype = npformat.read_array_header_1_0(fp)
    elif version == (2, 0):
        shape, fortran, dtype = npformat.read_array_header_2_0(fp)
    else:
        raise SolutionFormatError("Versão de .npy não suportada.")
    if dtype.hasobject:
        raise SolutionFormatError("O arquivo contém objetos Python (pickle) e foi recusado.")
    return shape, fortran, dtype


def import_npz(
    source: Path,
    directory: Path,
    control: Any = None,
    on_progress: Callable[[float], None] = _ignore,
) -> SolutionMeta:
    source, directory = Path(source), Path(directory)
    tmp = directory.with_name(directory.name + ".import.part")
    on_progress(0.0)
    try:
        try:
            zf = zipfile.ZipFile(source)
        except (zipfile.BadZipFile, OSError) as exc:
            raise SolutionFormatError(
                "O arquivo não é uma solução exportada (.npz) válida."
            ) from exc
        with zf:
            names = set(zf.namelist())
            missing = [n for n in (META_MEMBER, *(f"{a}.npy" for a in ARRAYS)) if n not in names]
            if missing:
                raise SolutionFormatError("Arquivo incompleto: faltam " + ", ".join(missing) + ".")
            with zf.open(META_MEMBER) as fp:
                _read_header(fp)
                try:
                    raw = json.loads(fp.read().decode())
                    meta = SolutionMeta(**raw)
                except (ValueError, TypeError) as exc:
                    raise SolutionFormatError("Metadados da solução inválidos.") from exc
            if meta.format_version != FORMAT_VERSION:
                raise IncompatibleVersionError(
                    f"Versão de formato {meta.format_version} não suportada "
                    f"(esperado {FORMAT_VERSION})."
                )
            names_to_copy = list(ARRAYS)
            tree_json = b""
            if "tree.json.npy" in names:
                tree_members = [f"tree_{n}" for n in TREE_ARRAYS]
                lacking = [m for m in tree_members if f"{m}.npy" not in names]
                if lacking:
                    raise SolutionFormatError(
                        "Árvore incompleta no arquivo: faltam " + ", ".join(lacking) + "."
                    )
                names_to_copy += tree_members
                with zf.open("tree.json.npy") as fp:
                    _read_header(fp)
                    tree_json = fp.read()
                try:
                    json.loads(tree_json.decode())
                except ValueError as exc:
                    raise SolutionFormatError("Metadados da árvore inválidos.") from exc
            infos = {a: zf.getinfo(f"{a}.npy") for a in names_to_copy}
            total = sum(i.file_size for i in infos.values()) or 1
            done = 0
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True)
            (tmp / "meta.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2))
            if tree_json:
                (tmp / "tree.json").write_bytes(tree_json)
            for name in names_to_copy:
                with zf.open(f"{name}.npy") as src, open(tmp / f"{name}.npy", "wb") as dst:
                    shape, fortran, dtype = _read_header(src)
                    header = {
                        "descr": npformat.dtype_to_descr(dtype),
                        "fortran_order": fortran,
                        "shape": shape,
                    }
                    npformat.write_array_header_1_0(dst, header)
                    expected = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
                    copied = 0
                    while True:
                        if _stop(control):
                            raise Cancelled()
                        buf = src.read(CHUNK_BYTES)
                        if not buf:
                            break
                        dst.write(buf)
                        copied += len(buf)
                        done += len(buf)
                        on_progress(min(0.999, done / total))
                    if copied != expected:
                        raise SolutionFormatError(
                            f"Array '{name}' corrompido (tamanho inesperado)."
                        )
        _check_consistency(tmp)
        if directory.exists():
            shutil.rmtree(directory)
        os.replace(tmp, directory)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    on_progress(1.0)
    return meta


def _check_consistency(d: Path) -> None:
    arrs = {n: np.load(d / f"{n}.npy", mmap_mode="r", allow_pickle=False) for n in ARRAYS}
    no, co = arrs["node_offsets"], arrs["combo_offsets"]
    ok = (
        no.ndim == 1
        and co.ndim == 1
        and no.shape == co.shape
        and int(no[-1]) == arrs["strategy"].shape[0]
        and int(co[-1]) == arrs["ev"].shape[0] == arrs["equity"].shape[0]
    )
    if not ok:
        raise SolutionFormatError("Arrays da solução inconsistentes entre si.")
