import duckdb
import pytest
from pydantic import ValidationError
from core.models import CoreMatchBaseModel
from core.database import query_models, query_model_or_none, execute_update, init_schema

class DummyModel(CoreMatchBaseModel):
    id: int
    name: str

def test_base_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DummyModel(id=1, name="Test", extra_prop=123)

def test_query_models_maps_rows(tmp_path):
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    con.execute("CREATE TABLE dummy (id INT, name VARCHAR)")
    con.execute("INSERT INTO dummy VALUES (1, 'Alice'), (2, 'Bob')")
    
    results = query_models(DummyModel, con, "SELECT * FROM dummy ORDER BY id")
    assert len(results) == 2
    assert results[0].name == "Alice"
    assert results[1].id == 2

