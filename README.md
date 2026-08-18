# NLP Pipeline API

![CI](https://github.com/Julian-Rincon/nlp-pipeline-api/actions/workflows/ci.yml/badge.svg)

API de procesamiento de lenguaje natural construida con **spaCy** y **FastAPI**, desplegada de dos formas distintas en **AWS** sobre exactamente el mismo pipeline: preprocesamiento → extracción de características → análisis (POS/NER/dependencias) → salida.

Proyecto académico — Procesamiento de Lenguaje Natural (PLN), Universidad Sergio Arboleda.

## Integrantes

- Andrés Castro
- Juan Hurtado
- Miguel Flechas
- Julián Rincón

## Arquitectura

Un único módulo de pipeline (`nlp_pipeline.py`) y una única app FastAPI (`main.py`) se despliegan de dos formas:

| Despliegue | Cómo corre | Entrypoint |
|---|---|---|
| **EC2 / AWS Cloud9** | Servicio systemd persistente, `uvicorn` sirviendo la app directamente | `main:app` vía `uvicorn` |
| **AWS Lambda** | Imagen de contenedor en ECR, invocada por Lambda a través de un Function URL | `lambda_handler.py` (adapta la app con [Mangum](https://mangum.io/)) |

Ambos despliegues ejecutan el **mismo código de pipeline** — no hay dos implementaciones divergentes.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Chequeo de salud |
| GET | `/` | Info de la API e integrantes |
| POST | `/processed` | Preprocessing: minúsculas, sin stopwords/puntuación, verbos lematizados |
| POST | `/dependency` | Árbol de dependencias sintácticas, visualizable en HTML (`?format=json` para JSON) |
| POST | `/ner` | Entidades nombradas resaltadas en HTML (`?format=json` para lista estructurada) |
| POST | `/full` | Pipeline completo en un solo llamado: tokens + POS + lemma + entidades + texto procesado |
| POST | `/encoding` | Feature extraction: One-hot, Bag-of-Words o TF-IDF (scikit-learn) sobre un corpus |

Body para `/processed`, `/dependency`, `/ner`, `/full`:
```json
{"text": "El gato come pescado en la cocina."}
```

Body para `/encoding`:
```json
{"texts": ["texto uno", "texto dos"], "method": "tfidf"}
```
`method` acepta `bow` (default), `tfidf` u `onehot`.

## Límites y decisiones de diseño

- Solo se sirve `es_core_news_sm` — el resto del pipeline (limpieza de repeticiones adversariales, límites de tamaño de texto/corpus) se probó bajo carga y casos adversariales antes de desplegar.
- Repeticiones de más de 4 del mismo carácter se colapsan a 3 antes de tokenizar: sin esto, texto adversarial (miles de signos repetidos) vuelve casi cuadrático al tokenizador de spaCy.
- Máximo 100.000 caracteres por texto y 200 documentos por corpus.

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

Se ejecutan automáticamente en CI (GitHub Actions) en cada push, junto con la validación del build de la imagen Docker de Lambda.

## Despliegue en AWS

**EC2/Cloud9** — corre como servicio `systemd` (`nlp-api.service`), reinicio automático ante fallos.

**Lambda** — imagen construida con el `Dockerfile` de este repo (`public.ecr.aws/lambda/python:3.11` base), subida a ECR y desplegada como función Lambda con Function URL público.

```bash
docker build -t nlp-lambda-api .
docker tag nlp-lambda-api:latest <cuenta>.dkr.ecr.<region>.amazonaws.com/nlp-lambda-api:latest
docker push <cuenta>.dkr.ecr.<region>.amazonaws.com/nlp-lambda-api:latest
```
