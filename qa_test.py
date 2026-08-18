"""
QA de casos límite y adversariales contra el contrato del laboratorio.
Uso: python3 qa_test.py <base_url>
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
print(f"Target: {BASE_URL}\n")
failures = []


def post(path, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def check(name, cond, detail=""):
    print(f"[{'OK' if cond else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not cond:
        failures.append(name)


print("=== 1) Sanidad de las 5 rutas del contrato ===")
status, _ = post("/api/v1/clean", {"text": "El gato come pescado."})
check("/api/v1/clean -> 200", status == 200, f"status={status}")
status, _ = post("/api/v1/pos", {"text": "El gato come pescado."})
check("/api/v1/pos -> 200", status == 200, f"status={status}")
status, _ = post("/api/v1/ner", {"text": "Apple está en Colombia."})
check("/api/v1/ner -> 200", status == 200, f"status={status}")
status, _ = post("/api/v1/visualize/dep", {"text": "El gato come pescado."})
check("/api/v1/visualize/dep -> 200", status == 200, f"status={status}")
status, _ = post("/api/v1/vectorize", {"documents": ["El gato come", "El perro come"]})
check("/api/v1/vectorize -> 200", status == 200, f"status={status}")

print("\n=== 2) Contrato de validación (todo debe dar 4xx, nunca 500) ===")
invalid_cases = [
    ("/api/v1/clean", {}),
    ("/api/v1/clean", {"text": None}),
    ("/api/v1/clean", {"text": 123}),
    ("/api/v1/clean", {"text": []}),
    ("/api/v1/clean", {"text": ""}),
    ("/api/v1/clean", {"text": "   "}),
    ("/api/v1/pos", {"text": ["ok", None]}),
    ("/api/v1/pos", {"text": ["ok", 42]}),
    ("/api/v1/pos", {"text": ["ok", "   "]}),  # lote con un inválido -> rechazo total
    ("/api/v1/visualize/dep", {"text": ["a", "b"]}),  # batch prohibido aquí
    ("/api/v1/vectorize", {"documents": ["solo uno"]}),
    ("/api/v1/vectorize", {"documents": []}),
]
for path, payload in invalid_cases:
    status, body = post(path, payload)
    ok = 400 <= status < 500
    check(f"{path} {payload} -> 4xx", ok, f"status={status}")
    if ok:
        try:
            has_partial = "results" in json.loads(body) or "cleaned_text" in json.loads(body)
            check(f"  sin resultados parciales", not has_partial)
        except Exception:
            pass

print("\n=== 3) Casos límite de contenido ===")
edge_cases = [
    ("emojis", "Texto con 🚀 emojis 😀"),
    ("html crudo", "<script>alert(1)</script>"),
    ("unicode raro", "Ñoño café niño 日本語 中文"),
    ("puntuación sin espacio", "hola,mundo;adios.chau"),
    ("repetido masivo", ("palabra repetida " * 2000).strip()),
]
for name, text in edge_cases:
    status, _ = post("/api/v1/clean", {"text": text})
    check(f"'{name}' -> 200", status == 200, f"status={status}")

print("\n=== 4) Adversarial: no debe colgarse ===")
t0 = time.time()
status, _ = post("/api/v1/clean", {"text": "¿" * 20_000 + "!" * 20_000})
dt = time.time() - t0
check("puntuación masiva no cuelga", status == 200 and dt < 10, f"status={status} tiempo={dt:.2f}s")

print("\n=== 5) Verificación del ejemplo de la guía (vectorize) ===")
docs = [
    "Mi gato, su gato y nuestro gato comen pescado",
    "Juan comió en Bogotá",
    "El caballo come muy rápido",
]
status, body = post("/api/v1/vectorize", {"documents": docs})
result = json.loads(body)
vocab = result["vocabulary"]
gato_idx = vocab.index("gato") if "gato" in vocab else -1
tfidf_gato = result["tf_idf"][0][gato_idx] if gato_idx >= 0 else None
check("vocabulario en orden lexicográfico", vocab == sorted(vocab))
check("TF-IDF(gato,d1) == 5.0794 (fórmula exacta de la guía)", tfidf_gato == 5.0794, f"obtenido={tfidf_gato}")

print("\n" + "=" * 60)
if failures:
    print(f"RESULTADO: {len(failures)} FALLO(S) -> {failures}")
else:
    print("RESULTADO: TODO OK — cumple el contrato de la guía.")
