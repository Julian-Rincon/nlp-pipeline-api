"""
Suite de regresión contra el contrato exacto de la guía del laboratorio
(Procesamiento_de_texto_con_spaCy_y_AWS.pdf, sección 8). Corre en CI contra
la app FastAPI en memoria, sin necesitar las APIs desplegadas en AWS.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# /api/v1/clean
# ---------------------------------------------------------------------------
def test_clean_texto_unico_devuelve_lista():
    r = client.post("/api/v1/clean", json={"text": "El Gato Come Pescado."})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["cleaned_text"], list)
    assert len(body["cleaned_text"]) == 1
    assert body["cleaned_text"][0] == "gato comer pescado" or "gato" in body["cleaned_text"][0]


def test_clean_minusculas_sin_stopwords_ni_puntuacion():
    r = client.post("/api/v1/clean", json={"text": "El Gato Come Pescado."})
    cleaned = r.json()["cleaned_text"][0]
    assert cleaned == cleaned.lower()
    assert "." not in cleaned
    assert "el" not in cleaned.split()


def test_clean_puntuacion_no_concatena_terminos():
    r = client.post("/api/v1/clean", json={"text": "hola,mundo"})
    cleaned = r.json()["cleaned_text"][0]
    assert cleaned == "hola mundo"


def test_clean_conserva_tildes_ene_digitos():
    r = client.post("/api/v1/clean", json={"text": "Niño camión 123"})
    cleaned = r.json()["cleaned_text"][0]
    assert "niño" in cleaned
    assert "camión" in cleaned
    assert "123" in cleaned


def test_clean_lote():
    r = client.post("/api/v1/clean", json={"text": ["El gato come.", "El perro corre."]})
    body = r.json()
    assert len(body["cleaned_text"]) == 2


# ---------------------------------------------------------------------------
# /api/v1/pos
# ---------------------------------------------------------------------------
def test_pos_estructura_y_orden():
    r = client.post("/api/v1/pos", json={"text": "El gato come."})
    body = r.json()
    tokens = body["results"][0]["tokens"]
    assert [t["text"] for t in tokens] == ["El", "gato", "come", "."]
    assert all({"text", "pos", "lemma"} <= t.keys() for t in tokens)


def test_pos_lote_correspondencia_por_indice():
    r = client.post("/api/v1/pos", json={"text": ["Yo corro.", "Tú saltas."]})
    results = r.json()["results"]
    assert len(results) == 2
    assert results[0]["tokens"][0]["text"] == "Yo"
    assert results[1]["tokens"][0]["text"] == "Tú"


# ---------------------------------------------------------------------------
# /api/v1/ner
# ---------------------------------------------------------------------------
def test_ner_devuelve_json_con_offsets():
    r = client.post("/api/v1/ner", json={"text": "Apple está en Colombia."})
    body = r.json()
    entities = body["results"][0]["entities"]
    assert any(e["label"] == "ORG" for e in entities)
    apple = next(e for e in entities if e["text"] == "Apple")
    assert apple["start"] == 0 and apple["end"] == 5


def test_ner_lote():
    r = client.post("/api/v1/ner", json={"text": ["Apple está en Colombia.", "Juan vive en Bogotá."]})
    assert len(r.json()["results"]) == 2


# ---------------------------------------------------------------------------
# /api/v1/visualize/dep
# ---------------------------------------------------------------------------
def test_visualize_dep_devuelve_html_con_svg():
    r = client.post("/api/v1/visualize/dep", json={"text": "El gato come pescado."})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<svg" in r.text


def test_visualize_dep_escapa_html_del_usuario():
    r = client.post("/api/v1/visualize/dep", json={"text": "<b>x</b>"})
    assert "&lt;b&gt;" in r.text


def test_visualize_dep_rechaza_lote():
    r = client.post("/api/v1/visualize/dep", json={"text": ["a", "b"]})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/vectorize
# ---------------------------------------------------------------------------
def test_vectorize_forma_y_orden():
    docs = ["El gato come pescado", "El perro come carne"]
    r = client.post("/api/v1/vectorize", json={"documents": docs})
    body = r.json()
    vocab = body["vocabulary"]
    assert vocab == sorted(vocab)  # orden lexicográfico ascendente
    assert len(body["bag_of_words"]) == 2
    assert len(body["bag_of_words"][0]) == len(vocab)
    assert len(body["tf_idf"]) == 2
    assert len(body["one_hot"]) == 2


def test_vectorize_ejemplo_de_la_guia():
    docs = [
        "Mi gato, su gato y nuestro gato comen pescado",
        "Juan comió en Bogotá",
        "El caballo come muy rápido",
    ]
    r = client.post("/api/v1/vectorize", json={"documents": docs})
    body = r.json()
    vocab = body["vocabulary"]
    gato_idx = vocab.index("gato")
    assert body["bag_of_words"][0][gato_idx] == 3
    assert body["tf_idf"][0][gato_idx] == 5.0794  # 3 * (ln(4/2)+1), redondeado a 4 decimales


def test_vectorize_one_hot_una_fila_por_ocurrencia():
    docs = ["gato gato perro", "gato"]
    r = client.post("/api/v1/vectorize", json={"documents": docs})
    body = r.json()
    assert len(body["one_hot"][0]) == 3  # 3 ocurrencias retenidas en doc 0 (ninguna es stopword)
    assert len(body["one_hot"][1]) == 1
    assert sum(body["one_hot"][0][0]) == 1  # cada fila es one-hot (un único 1)


def test_vectorize_rechaza_menos_de_dos_documentos():
    r = client.post("/api/v1/vectorize", json={"documents": ["solo uno"]})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Validación general (aplica a clean/pos/ner vía TextBatchIn)
# ---------------------------------------------------------------------------
def test_campo_ausente_da_4xx():
    r = client.post("/api/v1/clean", json={})
    assert 400 <= r.status_code < 500


def test_valor_null_da_4xx():
    r = client.post("/api/v1/clean", json={"text": None})
    assert 400 <= r.status_code < 500


def test_tipo_incorrecto_da_4xx():
    r = client.post("/api/v1/clean", json={"text": 123})
    assert 400 <= r.status_code < 500


def test_lista_vacia_da_4xx():
    r = client.post("/api/v1/clean", json={"text": []})
    assert 400 <= r.status_code < 500


def test_elemento_no_string_en_lote_da_4xx():
    r = client.post("/api/v1/pos", json={"text": ["hola", 42]})
    assert 400 <= r.status_code < 500


def test_texto_vacio_da_4xx():
    r = client.post("/api/v1/clean", json={"text": ""})
    assert 400 <= r.status_code < 500


def test_texto_solo_espacios_da_4xx():
    r = client.post("/api/v1/clean", json={"text": "   "})
    assert 400 <= r.status_code < 500


def test_lote_con_un_invalido_rechaza_todo_sin_resultados_parciales():
    r = client.post("/api/v1/pos", json={"text": ["texto válido", "   "]})
    assert 400 <= r.status_code < 500
    assert "results" not in r.json()


def test_puntuacion_adversarial_no_cuelga():
    r = client.post("/api/v1/clean", json={"text": "¿" * 20_000 + "!" * 20_000})
    assert r.status_code == 200


def test_texto_excede_limite_da_4xx():
    r = client.post("/api/v1/clean", json={"text": "a" * 100_001})
    assert 400 <= r.status_code < 500
