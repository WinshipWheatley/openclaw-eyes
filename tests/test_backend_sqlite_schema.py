import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_data_contract import (
    REQUIRED_SQLITE_TABLE_CONCEPTS,
    required_sqlite_table_concept_fields,
    sqlite_table_concept,
)
from backend_sqlite_schema import (
    INERT_SCHEMA_BOUNDARIES,
    SCHEMA_VERSION,
    SQLITE_SCHEMA_TABLES,
    SQLITE_SCHEMA_TABLE_NAMES,
    TableDefinition,
    required_contract_fields_for_table,
    sqlite_physical_schema_sql_definitions,
    sqlite_physical_schema_table,
    sqlite_physical_schema_table_names,
    sqlite_physical_schema_tables,
    sqlite_schema_control_table,
    sqlite_schema_control_table_names,
    sqlite_schema_control_tables,
    sqlite_schema_matches_backend_contract,
    sqlite_schema_sql_definitions,
    sqlite_schema_table,
    sqlite_schema_table_names,
    sqlite_schema_tables,
    table_retrieval_structure_fields,
    validate_sqlite_schema_table,
)


MODULE_PATH = Path(__file__).resolve().parents[1] / "backend_sqlite_schema.py"

EXPECTED_PRIMARY_KEYS = {
    "semantic_records": "record_id",
    "semantic_labels": "label_id",
    "semantic_relationships": "relationship_id",
    "provenance_refs": "provenance_ref_id",
    "validation_receipts": "receipt_id",
    "operator_promotions": "promotion_id",
    "context_filter_receipts": "context_filter_receipt_id",
}

TABLE_LEVEL_SQL_PREFIXES = (
    "PRIMARY ",
    "FOREIGN ",
    "CONSTRAINT ",
    "UNIQUE ",
    "CHECK ",
)


def module_ast() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def called_function_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def sql_column_lines(sql_text: str) -> tuple[str, ...]:
    lines = []
    for raw_line in sql_text.splitlines()[1:]:
        line = raw_line.strip().removesuffix(",")
        if line in {");", ")"}:
            continue
        if line.upper().startswith(TABLE_LEVEL_SQL_PREFIXES):
            continue
        lines.append(line)
    return tuple(lines)


def sql_column_names(sql_text: str) -> tuple[str, ...]:
    return tuple(line.split(maxsplit=1)[0] for line in sql_column_lines(sql_text))


def primary_key_column_names(sql_text: str) -> tuple[str, ...]:
    return tuple(
        line.split(maxsplit=1)[0]
        for line in sql_column_lines(sql_text)
        if "PRIMARY KEY" in line.upper()
    )


def test_module_is_inert_and_does_not_import_sqlite3():
    tree = module_ast()

    assert "sqlite3" not in imported_module_names(tree)
    assert {
        "connect",
        "execute",
        "executemany",
        "executescript",
        "cursor",
        "commit",
        "rollback",
        "open",
        "read_text",
        "write_text",
    }.isdisjoint(called_function_names(tree))

    assert set(INERT_SCHEMA_BOUNDARIES) >= {
        "no sqlite3 import",
        "no database connections",
        "no SQL execution",
        "no migrations",
        "no persistence",
        "no runtime file I/O",
        "no indexing",
        "no embeddings",
        "no PageIndex dependency",
    }


def test_all_seven_table_concepts_exist_in_contract_order():
    assert sqlite_schema_table_names() == REQUIRED_SQLITE_TABLE_CONCEPTS
    assert SQLITE_SCHEMA_TABLE_NAMES == (
        "semantic_records",
        "semantic_labels",
        "semantic_relationships",
        "provenance_refs",
        "validation_receipts",
        "operator_promotions",
        "context_filter_receipts",
    )
    assert len(sqlite_schema_tables()) == 7
    assert all(isinstance(table, TableDefinition) for table in SQLITE_SCHEMA_TABLES)


def test_schema_versions_is_separate_schema_control_metadata():
    assert SCHEMA_VERSION == "backend-sqlite-schema-definition-v1"
    assert sqlite_schema_control_table_names() == ("schema_versions",)
    assert "schema_versions" not in sqlite_schema_table_names()
    assert sqlite_schema_table("schema_versions") is None

    table = sqlite_schema_control_table("schema_versions")

    assert table is not None
    assert table.related_schema_contract_surface == "schema_control_metadata"
    assert table.retrieval_structure_fields == frozenset()
    assert table.column_names == (
        "schema_version",
        "schema_identity",
        "applied_at",
        "source_commit",
        "migration_state",
        "notes",
    )
    assert primary_key_column_names(table.create_table_sql) == ("schema_version",)
    assert sql_column_names(table.create_table_sql) == table.column_names
    assert "no migration runner" in table.forbidden_implementation_behavior
    assert "no file-backed database" in table.forbidden_implementation_behavior
    assert "no persistence" in table.forbidden_implementation_behavior


def test_physical_schema_includes_semantic_tables_plus_schema_control_metadata():
    assert sqlite_physical_schema_table_names() == sqlite_schema_table_names() + (
        "schema_versions",
    )
    assert sqlite_physical_schema_tables() == (
        sqlite_schema_tables() + sqlite_schema_control_tables()
    )
    assert sqlite_physical_schema_table("schema_versions") == sqlite_schema_control_table(
        "schema_versions"
    )
    assert sqlite_physical_schema_sql_definitions() == (
        sqlite_schema_sql_definitions()
        + tuple(table.create_table_sql for table in sqlite_schema_control_tables())
    )


def test_each_table_has_stable_name_columns_and_backend_contract_fields():
    for table in sqlite_schema_tables():
        concept = sqlite_table_concept(table.table_name)

        assert concept is not None
        assert table.related_schema_contract_surface == (
            concept.related_schema_contract_surface
        )
        assert table.column_names
        assert all(column.name for column in table.columns)
        assert required_contract_fields_for_table(table.table_name) == (
            required_sqlite_table_concept_fields(table.table_name)
        )
        assert table.conceptual_fields >= required_sqlite_table_concept_fields(
            table.table_name
        )
        assert validate_sqlite_schema_table(table) is True

    assert sqlite_schema_matches_backend_contract() is True


def test_sql_column_names_match_table_metadata_exactly():
    for table in sqlite_schema_tables():
        assert sql_column_names(table.create_table_sql) == table.column_names


def test_column_names_are_unique_per_table():
    for table in sqlite_schema_tables():
        assert len(table.column_names) == len(set(table.column_names))
        assert len(sql_column_names(table.create_table_sql)) == len(
            set(sql_column_names(table.create_table_sql))
        )


def test_each_table_has_exactly_one_stable_primary_key_column():
    assert set(EXPECTED_PRIMARY_KEYS) == set(sqlite_schema_table_names())

    for table in sqlite_schema_tables():
        assert primary_key_column_names(table.create_table_sql) == (
            EXPECTED_PRIMARY_KEYS[table.table_name],
        )


def test_required_contract_fields_are_backed_by_schema_columns():
    for table in sqlite_schema_tables():
        required_fields = required_sqlite_table_concept_fields(table.table_name)
        column_fields = {
            column.conceptual_field
            for column in table.columns
            if column.name in sql_column_names(table.create_table_sql)
        }

        assert required_fields <= column_fields


def test_hierarchy_provenance_relationship_and_promotion_fields_are_represented():
    semantic_records = sqlite_schema_table("semantic_records")
    provenance_refs = sqlite_schema_table("provenance_refs")
    relationships = sqlite_schema_table("semantic_relationships")
    promotions = sqlite_schema_table("operator_promotions")

    assert semantic_records is not None
    assert provenance_refs is not None
    assert relationships is not None
    assert promotions is not None

    assert {
        "document_hierarchy",
        "section_page_reference",
        "multilevel_summary",
    } <= semantic_records.conceptual_fields
    assert {
        "document_id",
        "parent_record_id",
        "section_path",
        "page_ref",
        "summary_level",
        "summary_text_ref",
    } <= set(semantic_records.column_names)

    assert {
        "provenance_ref_id",
        "source_basis",
        "source_set_ref",
        "manifest_ref",
        "bridge_ref",
        "packet_ref",
        "receipt_ref",
    } <= provenance_refs.conceptual_fields
    assert "relationship_edges" in relationships.conceptual_fields
    assert {
        "promotion_id",
        "operator_decision",
        "promotion_scope",
        "promoted_by_operator",
        "complete_label_set",
    } <= promotions.conceptual_fields


def test_labels_preserve_freshness_confidence_authority_sensitivity_and_review():
    records = sqlite_schema_table("semantic_records")
    labels = sqlite_schema_table("semantic_labels")
    validation = sqlite_schema_table("validation_receipts")
    context_filter = sqlite_schema_table("context_filter_receipts")

    assert records is not None
    assert labels is not None
    assert validation is not None
    assert context_filter is not None

    assert {
        "freshness_refs",
        "confidence_label",
        "authority_label",
        "sensitivity_label",
        "review_status_label",
    } <= set(records.column_names)
    assert {
        "label_name",
        "label_value",
        "label_basis",
        "review_status",
        "source_label_ref",
    } <= set(labels.column_names)
    assert {
        "label_name",
        "label_value",
        "label_basis",
        "review_status",
    } <= labels.conceptual_fields
    assert "provenance_refs" in labels.conceptual_fields
    assert "validation_result" in validation.conceptual_fields
    assert "filter_outcome" in context_filter.conceptual_fields
    assert "review_route" in context_filter.conceptual_fields


def test_sql_strings_are_inert_definitions_only():
    sql_definitions = sqlite_schema_sql_definitions()

    assert len(sql_definitions) == 7
    for table_name, sql_text in zip(sqlite_schema_table_names(), sql_definitions):
        assert sql_text.startswith(f"CREATE TABLE {table_name} (")
        assert sql_text.endswith(");")
        assert "INSERT " not in sql_text
        assert "UPDATE " not in sql_text
        assert "DELETE " not in sql_text
        assert "SELECT " not in sql_text
        assert "CREATE INDEX" not in sql_text

    assert sqlite_schema_sql_definitions.__code__.co_names == ("SQLITE_CREATE_TABLE_SQL",)


def test_physical_sql_strings_are_inert_definitions_only():
    sql_definitions = sqlite_physical_schema_sql_definitions()

    assert len(sql_definitions) == 8
    for table_name, sql_text in zip(sqlite_physical_schema_table_names(), sql_definitions):
        assert sql_text.startswith(f"CREATE TABLE {table_name} (")
        assert sql_text.endswith(");")
        assert "INSERT " not in sql_text
        assert "UPDATE " not in sql_text
        assert "DELETE " not in sql_text
        assert "SELECT " not in sql_text
        assert "CREATE INDEX" not in sql_text


def test_retrieval_structure_is_preserved_without_retrieval_implementation():
    assert table_retrieval_structure_fields("semantic_records") >= {
        "document_id",
        "parent_record_id",
        "section_path",
        "page_ref",
        "summary_level",
        "summary_text_ref",
    }
    assert table_retrieval_structure_fields("provenance_refs") >= {
        "document_id",
        "section_path",
        "page_ref",
    }
    assert table_retrieval_structure_fields("semantic_relationships") >= {
        "relationship_id",
        "authority_label",
        "sensitivity_label",
    }

    tree = module_ast()
    assert {
        "PageIndex",
        "RAG",
        "embedding",
        "vector",
        "index_document",
        "retrieve",
    }.isdisjoint(called_function_names(tree))


def test_unknown_table_lookup_fails_closed_without_side_effects():
    assert sqlite_schema_table("runtime_logs") is None
    assert table_retrieval_structure_fields("runtime_logs") == frozenset()
    assert required_contract_fields_for_table("runtime_logs") == frozenset()
