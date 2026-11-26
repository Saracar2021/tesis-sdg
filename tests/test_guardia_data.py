"""La guarda de tests/conftest.py impide que cualquier prueba abra, liste o escriba rutas bajo data/.

Estas pruebas fallan si la guarda deja de estar activa. Usan nombres que no existen, así que nunca se lee un dato
real aunque la guarda fallara.
"""
import os
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]

INEXISTENTE = "__guardia_no_existe__.csv"


@pytest.mark.parametrize("sub", ["reales_anon", "reales_crudos", "_privado", "consentimientos", "anotacion", ""])
def test_abrir_bajo_data_falla(sub):
    ruta = RAIZ / "data" / sub / INEXISTENTE
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        open(ruta, encoding="utf-8")
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        pd.read_csv(ruta)


def test_ruta_relativa_bajo_data_falla(monkeypatch):
    monkeypatch.chdir(RAIZ)
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        open(os.path.join("data", "reales_anon", INEXISTENTE))


def test_listar_y_escribir_bajo_data_falla():
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        list(os.scandir(RAIZ / "data"))                            # base de glob/rglob
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        os.listdir(RAIZ / "data" / "reales_anon")
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        open(RAIZ / "data" / "raw" / INEXISTENTE, "w")             # data/raw: solo lectura
    with pytest.raises(PermissionError, match="guarda de pruebas"):
        os.mkdir(RAIZ / "data" / "__guardia_dir__")


def test_lectura_en_data_raw_y_fuera_de_data_permitida(tmp_path):
    with pytest.raises(FileNotFoundError):                         # pasa la guarda; falla solo porque no existe
        open(RAIZ / "data" / "raw" / INEXISTENTE, encoding="utf-8")
    f = tmp_path / "x.csv"
    f.write_text("a\n1\n", encoding="utf-8")
    assert pd.read_csv(f)["a"].tolist() == [1]
