"""
API de procesamiento de texto — implementa el contrato de la guía del
laboratorio (Procesamiento_de_texto_con_spaCy_y_AWS.pdf, sección 8: "Perfil
mínimo de interoperabilidad del evaluador").

Este mismo archivo se despliega tal cual en las dos arquitecturas exigidas:
  - EC2 / Cloud9: uvicorn main:app (ver ec2/)
  - Lambda: envuelto con Mangum (ver lambda/lambda_handler.py)
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

import nlp_pipeline as nlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nlp_api")

app = FastAPI(
    title="NLP Text Processing API",
    description="Contrato del Laboratorio I - 2026 S02 (spaCy + AWS)",
    version="2.0.0",
)

# API pública de solo análisis de texto, sin autenticación ni datos sensibles.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_TEXT_LENGTH = 100_000
MAX_BATCH_SIZE = 500


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - t0) * 1000
    logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


def _validate_one(v: str, *, field: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{field}: cada elemento debe ser string")
    if len(v) > MAX_TEXT_LENGTH:
        raise ValueError(f"{field}: texto demasiado largo ({len(v)} chars), máximo {MAX_TEXT_LENGTH}")
    if not v.strip():
        raise ValueError(f"{field}: no puede estar vacío ni contener solo espacios")
    return v


class TextBatchIn(BaseModel):
    """Usada por /clean, /pos, /ner — text acepta un string o una lista de strings."""
    text: str | list[str]

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            _validate_one(v, field="text")
            return [v]
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("text: el lote no puede estar vacío")
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(f"text: lote demasiado grande ({len(v)}), máximo {MAX_BATCH_SIZE}")
        return [_validate_one(item, field="text") for item in v]


class DependencyIn(BaseModel):
    """Usada por /visualize/dep — un único string, nunca un lote."""
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        return _validate_one(v, field="text")


class VectorizeIn(BaseModel):
    documents: list[str]

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list) or len(v) < 2:
            raise ValueError("documents: se requieren al menos 2 documentos")
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(f"documents: lote demasiado grande ({len(v)}), máximo {MAX_BATCH_SIZE}")
        return [_validate_one(item, field="documents") for item in v]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/clean")
def clean(body: TextBatchIn):
    return {"cleaned_text": [nlp.clean_text_joined(t) for t in body.text]}


@app.post("/api/v1/pos")
def pos(body: TextBatchIn):
    return {"results": [{"tokens": nlp.pos_tokens(t)} for t in body.text]}


@app.post("/api/v1/ner")
def ner(body: TextBatchIn):
    return {"results": [{"entities": nlp.ner_entities(t)} for t in body.text]}


@app.post("/api/v1/visualize/dep", response_class=HTMLResponse)
def visualize_dep(body: DependencyIn):
    return nlp.dependency_svg_html(body.text)


@app.post("/api/v1/vectorize")
def vectorize(body: VectorizeIn):
    return nlp.vectorize(body.documents)
