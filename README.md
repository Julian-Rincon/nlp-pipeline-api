# NLP Text Processing API

![CI](https://github.com/Julian-Rincon/nlp-pipeline-api/actions/workflows/ci.yml/badge.svg)

Microservicio de procesamiento de lenguaje natural con **spaCy** y **FastAPI**, desplegado en dos arquitecturas de AWS Academy que exponen exactamente el mismo comportamiento funcional. Implementa el contrato definido en la guía **"Procesamiento de texto con spaCy y AWS"** (Laboratorio I - 2026 S02, PLN, Universidad Sergio Arboleda).

## Integrantes

- Andrés Castro
- Juan Hurtado
- Miguel Flechas
- Julián Rincón

## En vivo

| Despliegue | URL | Docs interactivas |
|---|---|---|
| **EC2 / Cloud9** | `http://<ip-actual>:8000` — ver [STATUS.md](STATUS.md) para la IP vigente | `http://<ip-actual>:8000/docs` |
| **Lambda + API Gateway** | `https://u04py63z34.execute-api.us-east-1.amazonaws.com` | [/docs](https://u04py63z34.execute-api.us-east-1.amazonaws.com/docs) |

> La instancia EC2 corre en una cuenta de AWS Academy Learner Lab: al reiniciarse la sesión (límite de 4h de Academy) la IP pública cambia porque **a propósito no usamos IP elástica** — costaría dinero del cupo mientras la instancia está apagada. En su lugar, la instancia se auto-reporta: al arrancar, un servicio systemd (`ec2/report-ip.service`) detecta su IP vía metadata (gratis) y actualiza [STATUS.md](STATUS.md) con un push automático a este repo. La URL de Lambda es estable y siempre funciona.
>
> **Nota sobre Lambda Function URL:** la guía pide exponer Lambda mediante Function URL. Lo intentamos a fondo — función nueva, permiso público `lambda:InvokeFunctionUrl` con `principal:"*"`, esperando hasta 2 minutos de propagación — y siempre devuelve `403 Forbidden`, incluso con la configuración textualmente correcta. Es un guardrail de la cuenta de AWS Academy que bloquea invocación anónima de Function URLs (no un error nuestro de configuración). Como alternativa **funcionalmente equivalente** — misma exposición HTTP pública, sin autenticación, sobre la misma función Lambda — usamos **API Gateway (HTTP API)** con integración proxy directa.

![Swagger UI de la API](assets/swagger_docs.png)

## Arquitectura

Un único módulo de pipeline (`nlp_pipeline.py`) y una única app FastAPI (`main.py`) contienen toda la lógica funcional, compartida entre los dos despliegues. Cada arquitectura tiene su propia carpeta con únicamente los archivos específicos de infraestructura:

```
aws_apis/
  nlp_pipeline.py   # lógica común: limpieza, POS, NER, dependencias, vectorización
  main.py           # app FastAPI compartida con las 5 rutas del contrato
  requirements.txt
  ec2/              # específico del despliegue EC2/Cloud9
    nlp-api.service       # unidad systemd que sirve main:app con uvicorn
    report-ip.service     # unidad systemd que auto-reporta la IP al arrancar
    report_ip.sh
  lambda/           # específico del despliegue Lambda
    Dockerfile             # build context = raíz del repo
    lambda_handler.py      # adapta la app FastAPI con Mangum
  tests/            # suite de regresión (pytest)
  qa_test.py, stress_test.py   # QA y capacidad/rendimiento contra una URL en vivo
```

| Despliegue | Cómo corre |
|---|---|
| **EC2 / AWS Cloud9** | Servicio systemd persistente (`ec2/nlp-api.service`), `uvicorn main:app` |
| **AWS Lambda** | Imagen de contenedor (`lambda/Dockerfile`) en ECR, invocada vía API Gateway; `lambda/lambda_handler.py` adapta la misma app FastAPI con [Mangum](https://mangum.io/) |

## Endpoints (contrato de la guía, sección 8)

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| POST | `/api/v1/clean` | `{"text": string \| string[]}` | `{"cleaned_text": string[]}` |
| POST | `/api/v1/pos` | `{"text": string \| string[]}` | `{"results": [{"tokens": [{"text","pos","lemma"}]}]}` |
| POST | `/api/v1/ner` | `{"text": string \| string[]}` | `{"results": [{"entities": [{"text","label","start","end"}]}]}` |
| POST | `/api/v1/visualize/dep` | `{"text": string}` (un único documento, **no acepta lote**) | `text/html` con SVG de displaCy embebido |
| POST | `/api/v1/vectorize` | `{"documents": string[]}` (mínimo 2) | `{"vocabulary","one_hot","bag_of_words","tf_idf"}` |

`text`/`documents` aceptan un string único o una lista — la posición `i` del resultado corresponde siempre al documento `i` de entrada. Todos los endpoints JSON reciben `Content-Type: application/json`. `/health` es auxiliar (no evaluado).

### Reglas de vectorización

- `vocabulary`: términos tras la limpieza, en **orden lexicográfico ascendente**.
- `bag_of_words[i][j]`: frecuencia absoluta del término `j` en el documento `i`.
- `one_hot[i]`: **una matriz por documento** — una fila por cada ocurrencia retenida (no una fila por documento), cada fila con un único `1` en la posición del término.
- `tf_idf[i][j] = tf(t,d) × idf(t)`, con `idf(t) = ln((|D|+1)/(n_t+1)) + 1`, **sin normalizar**, redondeado a 4 decimales.

### Ejemplo real (contra la API en Lambda)

```bash
$ curl -X POST https://u04py63z34.execute-api.us-east-1.amazonaws.com/api/v1/vectorize \
    -H "Content-Type: application/json" \
    -d '{"documents":["Mi gato, su gato y nuestro gato comen pescado","Juan comió en Bogotá","El caballo come muy rápido"]}'

{"vocabulary":["bogotá","caballo","come","comen","comió","gato","juan","pescado","rápido"],
 "bag_of_words":[[0,0,0,1,0,3,0,1,0], ...],
 "tf_idf":[[0.0,0.0,0.0,1.6931,0.0,5.0794,0.0,1.6931,0.0], ...],
 "one_hot":[[[0,0,0,0,0,1,0,0,0], ...], ...]}
```
`TF-IDF(gato, d1) = 3 × (ln(4/2)+1) = 5.0794` — verificado a mano contra la fórmula exacta de la guía.

### `/api/v1/visualize/dep` y `/api/v1/ner` en vivo

Salida real de `POST /api/v1/visualize/dep`:

![Árbol de dependencias](assets/dependency_tree.png)

`POST /api/v1/ner` devuelve JSON (no HTML); esta es una visualización de esas mismas entidades para referencia:

![Entidades nombradas](assets/ner_entities.png)

## Límites y decisiones de diseño

- Solo se sirve `es_core_news_sm`. Tres variantes del pipeline (`get_nlp_light`, `get_nlp_ner`, `get_nlp_dep`) excluyen `parser`/`ner` cuando no se necesitan, para no pagar ese costo en cada solicitud — ayuda directo al requisito de rendimiento (≤10s por solicitud).
- Repeticiones de más de 4 del mismo carácter se colapsan a 3 antes de tokenizar: sin esto, texto adversarial (miles de signos repetidos) vuelve casi cuadrático al tokenizador de spaCy.
- Máximo 100.000 caracteres por texto y 500 documentos por lote (la guía exige soportar al menos 25/10, dejamos margen amplio).
- La puntuación es su propio token en spaCy incluso pegada sin espacio (`"hola,mundo"` → `["hola", ",", "mundo"]`), así que al filtrarla en la limpieza los términos quedan naturalmente separados — sin riesgo de concatenación. Verificado en `tests/test_api.py`.
- `/vectorize` está implementado en Python puro (sin scikit-learn): el one-hot por-ocurrencia y el TF-IDF sin normalizar que pide la guía no son lo que scikit-learn entrega por defecto, y evitar esa dependencia también simplificó el build de la imagen Lambda (menos problemas de wheels nativos).
- CORS abierto (`*`) — es una API pública de solo análisis de texto, sin autenticación ni datos sensibles.
- Validación estricta y "todo o nada": cualquier campo ausente, `null`, tipo incorrecto, string vacío/solo-espacios, o elemento inválido dentro de un lote rechaza la solicitud completa con 4xx — nunca hay resultados parciales.

## Uso de inteligencia artificial generativa

Conforme a la sección 6 de la guía: se usó **Claude Code** (Anthropic) durante todo el desarrollo — diseño de la arquitectura, implementación de la API y el pipeline de spaCy, escritura de pruebas, automatización del despliegue en AWS (EC2/Cloud9 y Lambda) y depuración de errores (incluyendo la investigación del bloqueo de Function URL documentada arriba).

**Cómo se verificó:** cada endpoint se probó contra el contrato exacto de la guía con la suite `tests/test_api.py` (pytest, 27 casos incluyendo cada regla de validación), `qa_test.py` (casos límite y adversariales) y `stress_test.py` (capacidad de 25/10 documentos y concurrencia), corridos tanto en local como contra las dos URLs desplegadas en vivo antes de cada entrega. Los valores de TF-IDF se verificaron a mano contra la fórmula de la guía. El equipo revisó el código generado antes de incorporarlo.

## Correr localmente

```bash
pip install -r requirements.txt
python -m spacy download es_core_news_sm
uvicorn main:app --reload
```

Docs interactivas en `http://127.0.0.1:8000/docs`.

## Tests

```bash
pip install pytest httpx
python -m pytest tests/ -v
```

Se ejecutan automáticamente en CI (GitHub Actions) en cada push, junto con la validación del build de la imagen Docker de Lambda (`lambda/Dockerfile`).

### QA y capacidad contra una URL en vivo

```bash
python3 qa_test.py https://u04py63z34.execute-api.us-east-1.amazonaws.com
python3 stress_test.py https://u04py63z34.execute-api.us-east-1.amazonaws.com
```

`stress_test.py` cubre exactamente los requisitos de la sección 5 de la guía: 25 documentos de ~1000 caracteres a `/clean`, `/pos`, `/ner`; 10 documentos de ~1000 caracteres a `/vectorize`; y 30 solicitudes concurrentes (el mínimo exigido es 5). Resultado real de la última corrida contra Lambda:

```
=== 1) Capacidad: 25 documentos de ~1000 caracteres ===
/api/v1/clean con 25 docs -> 200 en <10s -> t=0.71s
/api/v1/pos con 25 docs -> 200 en <10s -> t=0.95s
/api/v1/ner con 25 docs -> 200 en <10s -> t=1.02s

=== 2) Capacidad: 10 documentos de ~1000 caracteres a vectorize ===
/api/v1/vectorize con 10 docs -> 200 en <10s -> t=0.52s

=== 3) Concurrencia: 30 solicitudes simultáneas ===
Completadas: 30/30 en 4.13s | p50=360ms p95=2698ms max=3654ms
RESULTADO: TODO OK
```

## Despliegue en AWS

```bash
# Lambda — build context es la raíz del repo
docker build -f lambda/Dockerfile -t nlp-lambda-api .
docker tag nlp-lambda-api:latest <cuenta>.dkr.ecr.<region>.amazonaws.com/nlp-lambda-api:latest
docker push <cuenta>.dkr.ecr.<region>.amazonaws.com/nlp-lambda-api:latest
```

EC2/Cloud9: `git pull`, `pip install -r requirements.txt`, copiar `ec2/*.service` a `/etc/systemd/system/`, `systemctl restart nlp-api`.
