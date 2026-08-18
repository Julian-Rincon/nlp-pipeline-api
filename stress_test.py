"""
Stress test + casos límite/adversariales contra una instancia en vivo de la
NLP Pipeline API. Uso: python3 stress_test.py <base_url>
"""
import concurrent.futures
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


def get(path, timeout=15):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as resp:
        return resp.status, resp.read()


def check(name, cond, detail=""):
    print(f"[{'OK' if cond else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not cond:
        failures.append(name)


print("=== 1) Sanidad de los 5 endpoints ===")
for path, payload in [
    ("/processed", {"text": "El gato come pescado."}),
    ("/dependency", {"text": "El gato come pescado."}),
    ("/ner", {"text": "Apple está en Colombia."}),
    ("/full", {"text": "El gato come pescado."}),
]:
    status, _ = post(path, payload)
    check(f"{path} responde 200", status == 200, f"status={status}")
status, _ = post("/encoding", {"texts": ["El gato come pescado", "El perro come carne"]})
check("/encoding responde 200", status == 200, f"status={status}")

print("\n=== 2) Casos límite ===")
edge_cases = [
    ("vacío", ""),
    ("solo espacios", "     "),
    ("emojis", "Texto con 🚀 emojis 😀 y símbolos €$%&#@"),
    ("html crudo", "<script>alert(1)</script><b>x</b>"),
    ("mezcla idiomas", "Hello mundo, this es una prueba mixta"),
    ("unicode raro", "Ñoño café niño über naïve 日本語 中文 العربية"),
    ("repetido masivo", ("palabra repetida " * 2000).strip()),
]
for name, text in edge_cases:
    status, body = post("/processed", {"text": text})
    check(f"'{name}' -> 200", status == 200, f"status={status}")

print("\n=== 3) Payloads adversariales (deben responder rápido, no colgarse) ===")
t0 = time.time()
status, _ = post("/processed", {"text": "¿" * 20_000 + "!" * 20_000})
dt = time.time() - t0
check("puntuación masiva (40k chars) no cuelga", status == 200 and dt < 20, f"status={status} tiempo={dt:.2f}s")

t0 = time.time()
status, _ = post("/processed", {"text": "a" * 50_000})
dt = time.time() - t0
check("token único de 50k chars no cuelga", status == 200 and dt < 20, f"status={status} tiempo={dt:.2f}s")

print("\n=== 4) Límites deben rechazar con 4xx, no 500 ===")
status, _ = post("/processed", {"text": "a" * 100_001})
check("texto > 100k chars -> 422", status == 422, f"status={status}")
status, _ = post("/processed", {"text": "hola", "model": "en_core_web_sm"})
check("modelo no soportado -> 422", status == 422, f"status={status}")
status, _ = post("/encoding", {"texts": ["hola"] * 201})
check("corpus > 200 docs -> 422", status == 422, f"status={status}")

print(f"\n=== 5) Estrés: 150 requests concurrentes (concurrencia=20) ===")
N, CONC = 150, 20
sample = "La inteligencia artificial está revolucionando la tecnología."


def one(i):
    t0 = time.time()
    status, _ = post("/processed", {"text": f"{sample} req {i}"}, timeout=30)
    return status, time.time() - t0


results = []
t_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for f in concurrent.futures.as_completed([ex.submit(one, i) for i in range(N)]):
        results.append(f.result())
total = time.time() - t_start
ok = sum(1 for s, _ in results if s == 200)
lat = sorted(d for _, d in results)
p50, p95 = lat[len(lat)//2], lat[int(len(lat)*0.95)]
print(f"Completadas: {len(results)}/{N} en {total:.2f}s ({len(results)/total:.1f} req/s)")
print(f"Éxitos 200: {ok}/{N} | p50={p50*1000:.0f}ms p95={p95*1000:.0f}ms max={max(lat)*1000:.0f}ms")
check("estrés concurrente: todas 200", ok == N, f"{ok}/{N}")

print("\n=== 6) El servidor sigue vivo tras todo esto ===")
status, _ = get("/health")
check("/health responde 200 tras la prueba completa", status == 200, f"status={status}")

print("\n" + "=" * 60)
if failures:
    print(f"RESULTADO: {len(failures)} FALLO(S) -> {failures}")
else:
    print("RESULTADO: TODO OK — API resiste carga, adversarios y casos límite.")
