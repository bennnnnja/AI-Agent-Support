from app.services.llm import get_llm


def test_llm_responds():
    llm = get_llm()
    response = llm.invoke("напиши слово 'математика' 10 раз")
    print(response.content)
    assert len(response.content) > 0