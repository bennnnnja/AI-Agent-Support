from app.services.rag import search_knowledge


def test_rag_responds():
    results = search_knowledge("принтер не печатает")
    print(results)
    assert len(results) > 0