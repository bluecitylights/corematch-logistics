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


def test_concurrent_get_db_access(tmp_path):
    import threading
    from core.database import get_db, close_master_connection
    
    test_db = str(tmp_path / "concurrent.duckdb")
    with get_db(test_db) as con:
        con.execute("CREATE TABLE concurrent_test (val INT)")
        
    errors = []
    def worker(val):
        try:
            with get_db(test_db) as con:
                con.execute("INSERT INTO concurrent_test VALUES (?)", [val])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    with get_db(test_db) as con:
        count = con.execute("SELECT COUNT(*) FROM concurrent_test").fetchone()[0]
        assert count == 15
    close_master_connection()


