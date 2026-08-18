"""
Stress test + verificación de capacidad/rendimiento exigidos por la guía:
- Limpieza/POS/NER: al menos 25 documentos de hasta 1000 caracteres, <10s.
- Vectorización: al menos 10 documentos de hasta 1000 caracteres, <10s.
- Al menos 5 solicitudes concurrentes independientes.
Uso: python3 stress_test.py <base_url>
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


def check(name, cond, detail=""):
    print(f"[{'OK' if cond else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not cond:
        failures.append(name)


sample_1000 = ("La inteligencia artificial y el procesamiento de lenguaje natural avanzan muy rápido. " * 12)[:1000]

print("=== 1) Capacidad: 25 documentos de ~1000 caracteres ===")
docs_25 = [f"{sample_1000} documento numero {i}" for i in range(25)]

t0 = time.time()
status, _ = post("/api/v1/clean", {"text": docs_25}, timeout=15)
check("/api/v1/clean con 25 docs -> 200 en <10s", status == 200 and (time.time() - t0) < 10, f"status={status} t={time.time()-t0:.2f}s")

t0 = time.time()
status, _ = post("/api/v1/pos", {"text": docs_25}, timeout=15)
check("/api/v1/pos con 25 docs -> 200 en <10s", status == 200 and (time.time() - t0) < 10, f"status={status} t={time.time()-t0:.2f}s")

t0 = time.time()
status, _ = post("/api/v1/ner", {"text": docs_25}, timeout=15)
check("/api/v1/ner con 25 docs -> 200 en <10s", status == 200 and (time.time() - t0) < 10, f"status={status} t={time.time()-t0:.2f}s")

print("\n=== 2) Capacidad: 10 documentos de ~1000 caracteres a vectorize ===")
docs_10 = [f"{sample_1000} documento numero {i}" for i in range(10)]
t0 = time.time()
status, _ = post("/api/v1/vectorize", {"documents": docs_10}, timeout=15)
check("/api/v1/vectorize con 10 docs -> 200 en <10s", status == 200 and (time.time() - t0) < 10, f"status={status} t={time.time()-t0:.2f}s")

print(f"\n=== 3) Concurrencia: al menos 5 solicitudes simultáneas (probamos con 30) ===")
N, CONC = 30, 15


def one(i):
    t0 = time.time()
    status, _ = post("/api/v1/clean", {"text": f"{sample_1000[:200]} req {i}"}, timeout=20)
    return status, time.time() - t0


results = []
t_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for f in concurrent.futures.as_completed([ex.submit(one, i) for i in range(N)]):
        results.append(f.result())
total = time.time() - t_start
ok = sum(1 for s, _ in results if s == 200)
lat = sorted(d for _, d in results)
print(f"Completadas: {len(results)}/{N} en {total:.2f}s ({len(results)/total:.1f} req/s)")
print(f"p50={lat[len(lat)//2]*1000:.0f}ms p95={lat[int(len(lat)*0.95)]*1000:.0f}ms max={max(lat)*1000:.0f}ms")
check("todas las concurrentes -> 200", ok == N, f"{ok}/{N}")

print("\n=== 4) El servicio sigue vivo tras todo esto ===")
status, _ = post("/api/v1/clean", {"text": "prueba final"})
check("/api/v1/clean responde tras la prueba completa", status == 200, f"status={status}")

print("\n" + "=" * 60)
if failures:
    print(f"RESULTADO: {len(failures)} FALLO(S) -> {failures}")
else:
    print("RESULTADO: TODO OK — cumple capacidad, rendimiento y concurrencia exigidos.")
