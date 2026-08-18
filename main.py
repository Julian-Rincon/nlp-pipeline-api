"""
API de preprocesamiento NLP (spaCy) — sigue el flujo de la diapositiva
"NLP Workflow": Raw text -> Preprocessing -> Feature Extraction -> Model -> Output.

Este mismo archivo se despliega tal cual en las dos APIs pedidas:
  - EC2 / Cloud9: uvicorn main:app
  - Lambda: envuelto con Mangum (ver lambda_handler.py)

Integrantes: Andrés Castro, Juan Hurtado, Miguel Flechas, Julián Rincón.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

import nlp_pipeline as nlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nlp_api")

app = FastAPI(
    title="NLP Pipeline API",
    description="Preprocesamiento con spaCy — Andrés Castro, Juan Hurtado, Miguel Flechas, Julián Rincón",
    version="1.0.0",
)

ALLOWED_MODELS = {"es_core_news_sm"}
MAX_TEXT_LENGTH = 100_000
MAX_CORPUS_SIZE = 200


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - t0) * 1000
    logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


class TextIn(BaseModel):
    text: str
    model: str = "es_core_news_sm"

    @field_validator("model")
    @classmethod
    def model_allowed(cls, v: str) -> str:
        if v not in ALLOWED_MODELS:
            raise ValueError(f"modelo no soportado, usa uno de: {sorted(ALLOWED_MODELS)}")
        return v

    @field_validator("text")
    @classmethod
    def text_within_length(cls, v: str) -> str:
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f"texto demasiado largo ({len(v)} chars), máximo {MAX_TEXT_LENGTH}")
        return v


class EncodingIn(BaseModel):
    texts: list[str]
    model: str = "es_core_news_sm"
    method: str = "bow"

    @field_validator("model")
    @classmethod
    def model_allowed(cls, v: str) -> str:
        if v not in ALLOWED_MODELS:
            raise ValueError(f"modelo no soportado, usa uno de: {sorted(ALLOWED_MODELS)}")
        return v

    @field_validator("method")
    @classmethod
    def method_allowed(cls, v: str) -> str:
        if v not in {"bow", "tfidf", "onehot"}:
            raise ValueError("method debe ser 'bow', 'tfidf' u 'onehot'")
        return v

    @field_validator("texts")
    @classmethod
    def texts_within_limits(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("texts no puede estar vacío")
        if len(v) > MAX_CORPUS_SIZE:
            raise ValueError(f"corpus demasiado grande ({len(v)} textos), máximo {MAX_CORPUS_SIZE}")
        for t in v:
            if len(t) > MAX_TEXT_LENGTH:
                raise ValueError(f"un texto del corpus excede {MAX_TEXT_LENGTH} chars")
        return v


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "api": "NLP Pipeline API",
        "integrantes": ["Andrés Castro", "Juan Hurtado", "Miguel Flechas", "Julián Rincón"],
        "endpoints": ["/processed", "/dependency", "/ner", "/full", "/encoding"],
    }


@app.post("/processed")
def processed(body: TextIn):
    return {"original": body.text, "processed": nlp.clean_and_transform(body.text, body.model)}


@app.post("/dependency")
def dependency(body: TextIn, format: str = "html"):
    if format == "json":
        doc_html = nlp.dependency_html(body.text, body.model)
        return {"original": body.text, "html": doc_html}
    return HTMLResponse(nlp.dependency_html(body.text, body.model))


@app.post("/ner")
def ner(body: TextIn, format: str = "html"):
    entities = nlp.ner_entities(body.text, body.model)
    if format == "json":
        return {"original": body.text, "entities": entities}
    return HTMLResponse(nlp.ner_html(body.text, body.model))


@app.post("/full")
def full(body: TextIn):
    return nlp.full_pipeline(body.text, body.model)


@app.post("/encoding")
def encoding(body: EncodingIn):
    return nlp.encode_corpus(body.texts, body.model, body.method)
