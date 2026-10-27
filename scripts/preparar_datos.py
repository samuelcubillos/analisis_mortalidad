"""
Preprocesamiento de los microdatos de Estadísticas Vitales (DANE) 2019.

Lee los tres archivos originales de data/raw/ y genera en data/processed/:
  - mortalidad_2019.csv.gz : una fila por defunción no fetal, con nombres de
    departamento, municipio, causa de muerte, sexo y grupo de edad ya unidos.
  - codigos_muerte.csv     : catálogo CIE-10 (código de 4 y 3 caracteres).

Se ejecuta una sola vez (python scripts/preparar_datos.py). La aplicación lee
el CSV comprimido para arrancar rápido y con poca memoria en el servidor.
"""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

SEXO = {"1": "Hombre", "2": "Mujer", "3": "Indeterminado"}

# Agrupación de GRUPO_EDAD1 según la tabla de referencia de la actividad
GRUPOS_EDAD = [
    (range(0, 5), "Mortalidad neonatal", "Menor de 1 mes"),
    (range(5, 7), "Mortalidad infantil", "1 a 11 meses"),
    (range(7, 9), "Primera infancia", "1 a 4 años"),
    (range(9, 11), "Niñez", "5 a 14 años"),
    (range(11, 12), "Adolescencia", "15 a 19 años"),
    (range(12, 14), "Juventud", "20 a 29 años"),
    (range(14, 17), "Adultez temprana", "30 a 44 años"),
    (range(17, 20), "Adultez intermedia", "45 a 59 años"),
    (range(20, 25), "Vejez", "60 a 84 años"),
    (range(25, 29), "Longevidad / Centenarios", "85 a 100+ años"),
    (range(29, 30), "Edad desconocida", "Sin información"),
]


def categoria_edad(codigo: int) -> str:
    for rango, nombre, _ in GRUPOS_EDAD:
        if codigo in rango:
            return nombre
    return "Edad desconocida"


def main() -> None:
    # 1. Defunciones no fetales 2019
    df = pd.read_excel(RAW / "NoFetal2019.xlsx", sheet_name="No_Fetales_2019", dtype=str)
    df["COD_DANE"] = df["COD_DANE"].str.zfill(5)
    df["COD_DEPARTAMENTO"] = df["COD_DEPARTAMENTO"].str.zfill(2)
    df["COD_MUERTE"] = df["COD_MUERTE"].str.strip().str.upper()

    # 2. Divipola: nombres de departamentos y municipios
    divi = pd.read_excel(RAW / "Divipola.xlsx", sheet_name="Hoja1", dtype=str)
    divi["COD_DANE"] = divi["COD_DANE"].str.zfill(5)
    divi["COD_DEPARTAMENTO"] = divi["COD_DEPARTAMENTO"].str.zfill(2)
    deptos = divi.drop_duplicates("COD_DEPARTAMENTO")[["COD_DEPARTAMENTO", "DEPARTAMENTO"]]
    munis = divi[["COD_DANE", "MUNICIPIO"]].drop_duplicates("COD_DANE")

    df = df.merge(deptos, on="COD_DEPARTAMENTO", how="left").merge(munis, on="COD_DANE", how="left")

    # 3. Catálogo CIE-10
    cod = pd.read_excel(RAW / "CodigosDeMuerte.xlsx", sheet_name="Final", header=8, dtype=str)
    cod.columns = ["CAPITULO", "NOMBRE_CAPITULO", "COD3", "DESC3", "COD4", "DESC4"]
    cod = cod.dropna(subset=["COD4"])
    for c in cod.columns:
        cod[c] = cod[c].str.strip()
    cod["COD4"] = cod["COD4"].str.upper()
    cod["COD3"] = cod["COD3"].str.upper()
    cod.to_csv(OUT / "codigos_muerte.csv", index=False)

    nombre4 = dict(zip(cod["COD4"], cod["DESC4"]))
    nombre3 = dict(zip(cod["COD3"], cod["DESC3"]))
    df["NOMBRE_CAUSA"] = df["COD_MUERTE"].map(nombre4).fillna(df["COD_MUERTE"].str[:3].map(nombre3))

    # 4. Variables derivadas
    df["SEXO_NOMBRE"] = df["SEXO"].map(SEXO).fillna("Indeterminado")
    df["GRUPO_EDAD1"] = df["GRUPO_EDAD1"].astype(int)
    df["CATEGORIA_EDAD"] = df["GRUPO_EDAD1"].apply(categoria_edad)
    df["MES"] = df["MES"].astype(int)

    cols = [
        "COD_DANE", "COD_DEPARTAMENTO", "DEPARTAMENTO", "MUNICIPIO", "MES",
        "SEXO_NOMBRE", "GRUPO_EDAD1", "CATEGORIA_EDAD", "MANERA_MUERTE",
        "COD_MUERTE", "NOMBRE_CAUSA",
    ]
    df[cols].to_csv(OUT / "mortalidad_2019.csv.gz", index=False, compression="gzip")

    print(f"Registros: {len(df):,}")
    print("Sin departamento:", df["DEPARTAMENTO"].isna().sum())
    print("Sin municipio:", df["MUNICIPIO"].isna().sum())
    print("Sin nombre de causa:", df["NOMBRE_CAUSA"].isna().sum())


if __name__ == "__main__":
    main()
