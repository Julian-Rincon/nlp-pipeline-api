import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8200"
failures = []


def post(path, payload, timeout=20):
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


# Los 5 endpoints responden 200 con texto normal
for path, payload in [
    ("/processed", {"text": "El gato come pescado."}),
    ("/dependency", {"text": "El gato come pescado."}),
    ("/ner", {"text": "Apple está en Colombia."}),
    ("/full", {"text": "El gato come pescado."}),
]:
    status, body = post(path, payload)
    check(f"{path} responde 200", status == 200, f"status={status}")

status, body = post("/encoding", {"texts": ["El gato come pescado", "El perro come carne"]})
check("/encoding responde 200", status == 200, f"status={status}")

# Modelo no soportado -> 422, no 500
status, body = post("/processed", {"text": "hola", "model": "en_core_web_sm"})
check("modelo no permitido -> 422", status == 422, f"status={status}")

# Texto vacío no rompe nada
for path in ["/processed", "/dependency", "/ner", "/full"]:
    status, body = post(path, {"text": ""})
    check(f"{path} con texto vacío -> 200", status == 200, f"status={status}")

# Encoding con lista vacía -> 422 controlado
status, body = post("/encoding", {"texts": []})
check("/encoding con lista vacía -> 422", status == 422, f"status={status}")

# Encoding con método inválido -> 422
status, body = post("/encoding", {"texts": ["hola"], "method": "no-existe"})
check("/encoding método inválido -> 422", status == 422, f"status={status}")

# Puntuación adversarial no cuelga (regresión conocida)
status, body = post("/processed", {"text": "¿" * 20000 + "!" * 20000})
check("puntuación adversarial no cuelga", status == 200, f"status={status}")

# Texto excede el límite -> 422
status, body = post("/processed", {"text": "a" * 100_001})
check("texto excede límite -> 422", status == 422, f"status={status}")

# XSS/HTML en /dependency queda escapado
status, body = post("/dependency", {"text": "<b>x</b>"})
check("HTML en /dependency queda escapado", status == 200 and b"&lt;b&gt;" in body, f"status={status}")

# /full: coherencia entre processed y tokens
status, body = post("/full", {"text": "El gato come pescado."})
result = json.loads(body)
check("/full incluye tokens, entities y processed", all(k in result for k in ("tokens", "entities", "processed", "original")))

print("\n" + "=" * 50)
if failures:
    print(f"RESULTADO: {len(failures)} FALLO(S) -> {failures}")
else:
    print("RESULTADO: TODO OK")
