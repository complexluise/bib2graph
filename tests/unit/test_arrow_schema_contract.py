"""Contrato de schema del Arrow que produce ``Corpus.to_arrow()`` (#296).

Atalaya (repo aparte, ADR 0050 §Constraints de Atalaya) **consume el Arrow**
que exporta bib2graph: nombres de columna, tipos y — para ``curation_status``
— el dominio de valores exacto. Si algo de eso cambia sin coordinar (rename,
cambio de tipo, o un valor nuevo/distinto en ``curation_status``), Atalaya se
rompe **en silencio** del otro lado (peor caso: el grafo de citas pierde
aristas porque ``source_id``/``references_id`` dejan de joinear).

Este test es el guardarraíl: congela la superficie load-bearing (golden
schema) para que ese tipo de cambio rompa el CI de **bib2graph**, ruidoso y
temprano, en vez de romper Atalaya sin que nadie se entere. Un fallo acá
significa: coordiná el cambio con Atalaya antes de mergear (ver #296 y
ADR 0050).

Diseño deliberado: el test NO congela el conjunto completo de columnas de
``CORPUS_SCHEMA``, solo el subconjunto que Atalaya efectivamente lee (la
"superficie a congelar" de #296). Agregar columnas nuevas a ``CORPUS_SCHEMA``
es libre y NO debe romper este test (verificado explícitamente más abajo).

Marcador: ``unit`` (sin red, sin I/O) — default del repo.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

_LIST_STR = pa.list_(pa.string())

# ---------------------------------------------------------------------------
# Golden schema — superficie load-bearing para Atalaya (#296)
# ---------------------------------------------------------------------------
#
# Nombre de columna -> tipo pyarrow esperado. Derivado de CORPUS_SCHEMA en
# schemas.py (la fuente canónica); este dict es una copia congelada de SOLO
# las columnas que Atalaya lee, no de las 23 columnas de CORPUS_SCHEMA.
#
# Todas las columnas listadas en el issue #296 ("INGESTED_COLUMNS") existen
# hoy en CORPUS_SCHEMA — no hay columnas "futuras" pendientes que comentar.
GOLDEN_ARROW_SCHEMA: dict[str, pa.DataType] = {
    # Identificadores — source_id/references_id deben ser el MISMO namespace
    # (ids OpenAlex "W..."): el grafo de citas de Atalaya joinea
    # references_id de un paper contra source_id de otro.
    Col.ID: pa.string(),
    Col.DOI: pa.string(),
    Col.SOURCE_ID: pa.string(),
    Col.REFERENCES_ID: _LIST_STR,
    Col.REFERENCES_DOI: _LIST_STR,
    # Metadatos bibliográficos
    Col.TITLE: pa.string(),
    Col.YEAR: pa.int32(),
    Col.ABSTRACT: pa.string(),
    Col.SOURCE: pa.string(),
    # Curación y procedencia
    Col.CURATION_STATUS: pa.string(),
    Col.IS_SEED: pa.bool_(),
    Col.PROVENANCE: pa.string(),
    # Autores
    Col.AUTHORS_RAW: _LIST_STR,
    Col.AUTHORS_ID: _LIST_STR,
    Col.AUTHORS_AFFILIATIONS: _LIST_STR,
    # Keywords
    Col.KEYWORDS_RAW: _LIST_STR,
    Col.KEYWORDS_ID: _LIST_STR,
    # Instituciones
    Col.INSTITUTIONS_RAW: _LIST_STR,
    Col.INSTITUTIONS_ID: _LIST_STR,
}

# Dominio exacto de curation_status que Atalaya espera (constraint duro del
# lado Postgres: check-constraint sobre estos tres valores).
GOLDEN_CURATION_STATUS_DOMAIN = frozenset({"candidate", "accepted", "rejected"})


def _make_minimal_row(**overrides: object) -> dict[str, object]:
    """Fila mínima válida con todos los campos de CORPUS_SCHEMA."""
    row: dict[str, object] = {
        "id": "doi:aabbccdd11223344",
        "source_id": "W12345",
        "doi": "10.1000/xyz123",
        "title": "Intercambio ecológico desigual",
        "year": 2020,
        "abstract": None,
        "source": "openalex",
        "language": "es",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": ["Jane Doe"],
        "authors_id": ["A123"],
        "authors_affiliations": ["MIT"],
        "keywords_raw": ["ecology"],
        "keywords_id": ["K1"],
        "institutions_raw": ["MIT"],
        "institutions_id": ["I1"],
        "references_id": ["W99999"],
        "references_doi": ["10.9999/ref1"],
        "cited_by_id": None,
    }
    row.update(overrides)
    return row


@pytest.fixture()
def corpus_de_prueba() -> Corpus:
    """Corpus mínimo con un paper, construido con el schema canónico real."""
    table = pa.Table.from_pylist([_make_minimal_row()], schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


class TestArrowSchemaContract:
    """Congela nombre + tipo de las columnas que Atalaya lee del Arrow."""

    def test_golden_columns_present_with_exact_name_and_type(
        self, corpus_de_prueba: Corpus
    ) -> None:
        """Cada columna del golden schema existe con nombre y tipo exactos.

        Falla ruidoso y específico si una columna:
        - falta (fue eliminada o renombrada),
        - cambió de tipo (p. ej. de list[str] a str).
        """
        table = corpus_de_prueba.to_arrow()
        actual_fields = {f.name: f.type for f in table.schema}

        errores: list[str] = []
        for col_name, expected_type in GOLDEN_ARROW_SCHEMA.items():
            if col_name not in actual_fields:
                errores.append(
                    f"Columna '{col_name}' AUSENTE en el Arrow exportado "
                    f"(¿renombrada o eliminada? Atalaya la consume — "
                    f"coordinar antes de romper, ver #296/ADR 0050)."
                )
                continue
            actual_type = actual_fields[col_name]
            if not actual_type.equals(expected_type):
                errores.append(
                    f"Columna '{col_name}' cambió de tipo: se esperaba "
                    f"{expected_type!s}, se encontró {actual_type!s}. "
                    f"Atalaya asume el tipo anterior — coordinar antes de "
                    f"romper (ver #296/ADR 0050)."
                )

        assert not errores, "Contrato de schema Arrow violado:\n" + "\n".join(errores)

    def test_curation_status_domain_is_exactly_candidate_accepted_rejected(
        self,
    ) -> None:
        """El dominio de valores de curation_status es exactamente el esperado.

        Contra el enum del código (fuente de verdad), no contra datos: si se
        agrega/quita/renombra un valor en ``CurationStatus``, este test lo
        detecta sin necesitar una fila con ese valor.
        """
        actual_domain = frozenset(c.value for c in CurationStatus)
        assert actual_domain == GOLDEN_CURATION_STATUS_DOMAIN, (
            f"Dominio de CurationStatus cambió: se esperaba "
            f"{sorted(GOLDEN_CURATION_STATUS_DOMAIN)}, se encontró "
            f"{sorted(actual_domain)}. Atalaya tiene un check-constraint "
            f"sobre estos valores exactos — coordinar antes de romper "
            f"(ver #296/ADR 0050)."
        )

    def test_curation_status_column_values_stay_within_domain(
        self, corpus_de_prueba: Corpus
    ) -> None:
        """Los valores reales en la columna curation_status respetan el dominio.

        Complementa el test anterior (que verifica el enum) verificando que
        los datos efectivamente exportados no contienen valores fuera del
        dominio esperado.
        """
        table = corpus_de_prueba.to_arrow()
        valores = set(table.column(Col.CURATION_STATUS).to_pylist())
        fuera_de_dominio = valores - GOLDEN_CURATION_STATUS_DOMAIN
        assert not fuera_de_dominio, (
            f"Valores de curation_status fuera del dominio contractual: "
            f"{sorted(fuera_de_dominio)}"
        )

    def test_adding_new_columns_does_not_break_the_contract(
        self, corpus_de_prueba: Corpus
    ) -> None:
        """Agregar columnas nuevas a CORPUS_SCHEMA es libre y seguro (#296 DoD).

        Diseño: el contrato es un chequeo de SUBCONJUNTO (cada columna del
        golden debe existir con nombre+tipo exactos), no de conjunto exacto.
        Este test lo deja explícito construyendo una tabla con una columna
        extra sintética y verificando que el mismo criterio de validación
        (mismo bucle que el test de arriba) sigue pasando sin objetar la
        columna nueva.
        """
        table = corpus_de_prueba.to_arrow()
        tabla_con_columna_nueva = table.append_column(
            "future_atalaya_field", pa.array([None], type=pa.string())
        )
        actual_fields = {f.name: f.type for f in tabla_con_columna_nueva.schema}

        # Mismo criterio que el contrato principal: solo importa que las
        # columnas del golden estén, con su tipo — la columna nueva no
        # participa del chequeo y no lo rompe.
        for col_name, expected_type in GOLDEN_ARROW_SCHEMA.items():
            assert col_name in actual_fields
            assert actual_fields[col_name].equals(expected_type)
        assert "future_atalaya_field" in actual_fields, (
            "La columna nueva debería seguir presente (no se descarta)."
        )

    def test_golden_schema_columns_are_subset_of_corpus_schema(self) -> None:
        """Todas las columnas del golden existen hoy en CORPUS_SCHEMA (no inventadas).

        Guardarraíl inverso: si alguien agrega una columna al golden que no
        existe en el schema canónico real, este test lo detecta (evita que
        el golden fixture se desincronice de la fuente de verdad en
        schemas.py).
        """
        corpus_schema_names = {f.name for f in CORPUS_SCHEMA}
        golden_names = set(GOLDEN_ARROW_SCHEMA)
        faltantes = golden_names - corpus_schema_names
        assert not faltantes, (
            f"Columnas del golden schema que NO existen en CORPUS_SCHEMA: "
            f"{sorted(faltantes)} — el golden se desincronizó de la fuente "
            f"de verdad real."
        )
