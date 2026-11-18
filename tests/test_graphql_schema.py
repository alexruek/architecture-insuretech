"""5.1-5.5: схема GraphQL client-info эквивалентна Swagger-контракту REST API v1."""

import pytest
from graphql import build_schema, graphql_sync, parse, validate

SCHEMA_PATH = ("Task5", "schema.graphql")

# Поля определений Client, Document, Relative из Swagger-контракта и их типы.
SWAGGER_DEFINITIONS = {
    "Client": {"id": "string", "name": "string", "age": "integer"},
    "Document": {
        "id": "string",
        "type": "string",
        "number": "string",
        "issueDate": "string",
        "expiryDate": "string",
    },
    "Relative": {
        "id": "string",
        "relationType": "string",
        "name": "string",
        "age": "integer",
    },
}
SWAGGER_SCALARS = {"string": "String", "integer": "Int"}

REST_PATHS = ("/clients/{id}", "/clients/{id}/documents", "/clients/{id}/relatives")

# Запросы, которыми выражаются три операции REST и их сочетание.
QUERY_CLIENT = 'query { client(id: "c1") { id name age } }'
QUERY_DOCUMENTS = 'query { client(id: "c1") { documents { id type number issueDate expiryDate } } }'
QUERY_RELATIVES = 'query { client(id: "c1") { relatives { id relationType name age } } }'
QUERY_COMBINED = """
query ClientCard($id: ID!) {
  client(id: $id) {
    name
    documents { type number }
    relatives { relationType name }
  }
}
"""

CLIENTS = {
    "c1": {
        "id": "c1",
        "name": "Иванов Иван Иванович",
        "age": 35,
        "documents": [
            {
                "id": "d1",
                "type": "passport",
                "number": "4510 123456",
                "issueDate": "2015-06-01",
                "expiryDate": "2035-06-01",
            }
        ],
        "relatives": [{"id": "r1", "relationType": "spouse", "name": "Иванова Мария", "age": 33}],
    }
}


class Root:
    @staticmethod
    def client(_info, id):
        return CLIENTS.get(id)


@pytest.fixture(scope="module")
def schema_text(repo_root):
    return repo_root.joinpath(*SCHEMA_PATH).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def schema(schema_text):
    return build_schema(schema_text)


def run(schema, query, variables=None):
    result = graphql_sync(schema, query, root_value=Root(), variable_values=variables)
    assert result.errors is None, result.errors
    return result.data


def test_schema_builds(schema):
    assert schema.query_type.name == "Query"


@pytest.mark.parametrize("type_name", sorted(SWAGGER_DEFINITIONS))
def test_type_fields_match_swagger(schema, type_name):
    graphql_type = schema.get_type(type_name)
    assert graphql_type is not None, f"нет типа {type_name}"
    for field, swagger_type in SWAGGER_DEFINITIONS[type_name].items():
        assert field in graphql_type.fields, f"{type_name}.{field}"
        field_type = str(graphql_type.fields[field].type)
        expected = "ID!" if field == "id" else SWAGGER_SCALARS[swagger_type]
        assert field_type == expected, f"{type_name}.{field}"


def test_type_has_no_fields_beyond_contract(schema):
    assert set(schema.get_type("Document").fields) == set(SWAGGER_DEFINITIONS["Document"])
    assert set(schema.get_type("Relative").fields) == set(SWAGGER_DEFINITIONS["Relative"])
    extra = set(schema.get_type("Client").fields) - set(SWAGGER_DEFINITIONS["Client"])
    assert extra == {"documents", "relatives"}


@pytest.mark.parametrize("field, item", [("documents", "Document"), ("relatives", "Relative")])
def test_nested_lists(schema, field, item):
    assert str(schema.get_type("Client").fields[field].type) == f"[{item}!]!"


def test_single_query_without_twins(schema):
    # 5.4: один запрос client, отдельных запросов под документы и родственников нет.
    fields = schema.query_type.fields
    assert list(fields) == ["client"]
    client = fields["client"]
    assert str(client.type) == "Client"
    assert list(client.args) == ["id"]
    assert str(client.args["id"].type) == "ID!"


def test_only_queries(schema):
    # Swagger-контракт содержит только GET, поэтому мутаций и подписок нет.
    assert schema.mutation_type is None
    assert schema.subscription_type is None


@pytest.mark.parametrize("path", REST_PATHS)
def test_rest_operation_documented(schema_text, path):
    assert path in schema_text


@pytest.mark.parametrize("query", [QUERY_CLIENT, QUERY_DOCUMENTS, QUERY_RELATIVES, QUERY_COMBINED])
def test_rest_operations_are_valid_queries(schema, query):
    assert validate(schema, parse(query)) == []


def test_client_operation(schema):
    assert run(schema, QUERY_CLIENT) == {
        "client": {"id": "c1", "name": "Иванов Иван Иванович", "age": 35}
    }


def test_documents_operation(schema):
    data = run(schema, QUERY_DOCUMENTS)
    assert data == {"client": {"documents": CLIENTS["c1"]["documents"]}}


def test_relatives_operation(schema):
    data = run(schema, QUERY_RELATIVES)
    assert data == {"client": {"relatives": CLIENTS["c1"]["relatives"]}}


def test_combined_query_returns_only_requested_fields(schema):
    data = run(schema, QUERY_COMBINED, {"id": "c1"})
    assert data == {
        "client": {
            "name": "Иванов Иван Иванович",
            "documents": [{"type": "passport", "number": "4510 123456"}],
            "relatives": [{"relationType": "spouse", "name": "Иванова Мария"}],
        }
    }


def test_unknown_client_is_null(schema):
    assert run(schema, 'query { client(id: "nope") { id } }') == {"client": None}


def test_unknown_field_is_rejected(schema):
    errors = validate(schema, parse('query { client(id: "c1") { passportScan } }'))
    assert errors


def test_task5_contains_only_schema(repo_root):
    # 5.5: выводы по заданию в решение не включаются.
    files = sorted(
        path.name
        for path in (repo_root / "Task5").rglob("*")
        if path.is_file() and path.name not in {".DS_Store", "Thumbs.db"}
    )
    assert files == ["schema.graphql"]
