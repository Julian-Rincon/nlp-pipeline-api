"""
Suite de regresión de la NLP Pipeline API. Corre en CI (GitHub Actions) contra
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
    assert r.json() == {"status": "ok"}


def test_root_lista_endpoints_e_integrantes():
    r = client.get("/")
    body = r.json()
    assert set(body["endpoints"]) == {"/processed", "/dependency", "/ner", "/full", "/encoding"}
    assert len(body["integrantes"]) == 4


def test_processed_limpia_y_transforma():
    r = client.post("/processed", json={"text": "El gato come pescado."})
    assert r.status_code == 200
    body = r.json()
    assert "gato" in body["processed"]
    assert "pescado" in body["processed"]
    assert "el" not in body["processed"].split()


def test_full_incluye_tokens_entidades_y_processed():
    r = client.post("/full", json={"text": "Apple está en Colombia."})
    assert r.status_code == 200
    body = r.json()
    assert all(k in body for k in ("original", "processed", "tokens", "entities"))
    assert any(e["label"] == "ORG" for e in body["entities"])


def test_dependency_devuelve_html_por_defecto():
    r = client.post("/dependency", json={"text": "El gato come pescado."})
    assert r.status_code == 200
    assert "<svg" in r.text


def test_dependency_escapa_html_del_usuario():
    r = client.post("/dependency", json={"text": "<b>x</b>"})
    assert "&lt;b&gt;" in r.text


def test_ner_json_devuelve_entidades():
    r = client.post("/ner?format=json", json={"text": "Apple está en Colombia."})
    body = r.json()
    labels = {e["label"] for e in body["entities"]}
    assert "ORG" in labels or "LOC" in labels


def test_encoding_bow():
    r = client.post("/encoding", json={"texts": ["El gato come pescado", "El perro come carne"]})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "bow"
    assert len(body["vectors"]) == 2


def test_modelo_no_soportado_da_422():
    r = client.post("/processed", json={"text": "hola", "model": "en_core_web_sm"})
    assert r.status_code == 422


def test_texto_excede_limite_da_422():
    r = client.post("/processed", json={"text": "a" * 100_001})
    assert r.status_code == 422


def test_encoding_lista_vacia_da_422():
    r = client.post("/encoding", json={"texts": []})
    assert r.status_code == 422


def test_puntuacion_adversarial_no_cuelga():
    r = client.post("/processed", json={"text": "¿" * 20_000 + "!" * 20_000})
    assert r.status_code == 200
