"""
Pipeline compartido de spaCy — usado tal cual por las dos APIs (EC2/Cloud9 y
Lambda) para garantizar que ambas cumplan el mismo contrato funcional exigido
por la guía del laboratorio (Procesamiento_de_texto_con_spaCy_y_AWS.pdf).
"""
import html
import math
import re
from functools import lru_cache

import spacy
from spacy.language import Language

_REPEAT_RE = re.compile(r"(.)\1{4,}")
_PUNCT_SPLIT_RE = re.compile(r"[^\w\s]|_", re.UNICODE)

MODEL = "es_core_news_sm"


def _sanitize(text: str) -> str:
    """Colapsa repeticiones excesivas de un mismo carácter a un máximo de 3.
    Sin esto, el tokenizador de spaCy se vuelve casi cuadrático ante basura
    adversarial (miles de signos repetidos) — vector de bloqueo real detectado en QA."""
    return _REPEAT_RE.sub(lambda m: m.group(1) * 3, text)


@lru_cache(maxsize=1)
def get_nlp_light() -> Language:
    """Sin parser ni ner — para /clean, /pos y /vectorize (no los necesitan)."""
    return spacy.load(MODEL, exclude=["parser", "ner"])


@lru_cache(maxsize=1)
def get_nlp_ner() -> Language:
    """Sin parser, con ner — para /ner."""
    return spacy.load(MODEL, exclude=["parser"])


@lru_cache(maxsize=1)
def get_nlp_dep() -> Language:
    """Con parser, sin ner — para /visualize/dep."""
    return spacy.load(MODEL, exclude=["ner"])


# ---------------------------------------------------------------------------
# /clean — minúsculas, sin puntuación ni stopwords, espacios normalizados.
# El tokenizador de es_core_news_sm NO separa toda la puntuación pegada sin
# espacio (",": y ":" sí, pero ".", ";", "-", "!", "(", ")" quedan fusionados
# al término vecino, ej. "casa.perro" -> un solo token "casa.perro"). Por eso
# reemplazamos cualquier carácter no alfanumérico/no-espacio por un espacio
# ANTES de tokenizar, garantizando que la puntuación siempre actúe como
# separador tal como exige la guía, sin depender del comportamiento interno
# del tokenizador.
# ---------------------------------------------------------------------------
def clean_tokens(text: str) -> list[str]:
    spaced = _PUNCT_SPLIT_RE.sub(" ", _sanitize(text))
    doc = get_nlp_light()(spaced)
    return [t.text.lower() for t in doc if not t.is_stop and not t.is_punct and not t.is_space]


def clean_text_joined(text: str) -> str:
    return " ".join(clean_tokens(text))


# ---------------------------------------------------------------------------
# /pos — tokens + POS + lema sobre el texto ORIGINAL (sin limpiar), orden
# preservado, incluye puntuación como en el texto fuente.
# ---------------------------------------------------------------------------
def pos_tokens(text: str) -> list[dict]:
    doc = get_nlp_light()(_sanitize(text))
    return [{"text": t.text, "pos": t.pos_, "lemma": t.lemma_} for t in doc]


# ---------------------------------------------------------------------------
# /ner — entidades sobre el texto original. start inclusivo, end exclusivo
# (comportamiento nativo de ent.start_char / ent.end_char).
# ---------------------------------------------------------------------------
def ner_entities(text: str) -> list[dict]:
    doc = get_nlp_ner()(_sanitize(text))
    return [
        {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in doc.ents
    ]


# ---------------------------------------------------------------------------
# /visualize/dep — HTML válido con el SVG de displaCy embebido. Un único
# documento por solicitud (el contrato prohíbe lotes aquí).
# ---------------------------------------------------------------------------
def dependency_svg_html(text: str) -> str:
    from spacy import displacy

    doc = get_nlp_dep()(_sanitize(text))
    svg = displacy.render(doc, style="dep", jupyter=False, options={"distance": 110, "compact": True})
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Análisis de dependencias</title></head>
<body style="font-family:sans-serif;padding:24px">
<h2>Análisis de dependencias</h2>
<p><b>Texto:</b> {html.escape(text)}</p>
<div style="overflow-x:auto">{svg}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# /vectorize — vocabulario común + One-Hot, Bag of Words y TF-IDF, calculados
# a mano según las reglas exactas de la sección 4 de la guía (sin sklearn:
# el one-hot por-ocurrencia y el TF-IDF sin normalizar no son lo que sklearn
# entrega por defecto).
# ---------------------------------------------------------------------------
def vectorize(documents: list[str]) -> dict:
    cleaned = [clean_tokens(d) for d in documents]
    vocabulary = sorted({tok for doc in cleaned for tok in doc})
    index = {term: i for i, term in enumerate(vocabulary)}
    v_size = len(vocabulary)
    n_docs = len(documents)

    bag_of_words = []
    one_hot = []
    for doc in cleaned:
        bow_row = [0] * v_size
        onehot_matrix = []
        for tok in doc:
            j = index[tok]
            bow_row[j] += 1
            onehot_row = [0] * v_size
            onehot_row[j] = 1
            onehot_matrix.append(onehot_row)
        bag_of_words.append(bow_row)
        one_hot.append(onehot_matrix)

    doc_term_sets = [set(doc) for doc in cleaned]
    idf = []
    for term in vocabulary:
        n_t = sum(1 for terms in doc_term_sets if term in terms)
        idf.append(math.log((n_docs + 1) / (n_t + 1)) + 1)

    tf_idf = [
        [round(bag_of_words[i][j] * idf[j], 4) for j in range(v_size)]
        for i in range(n_docs)
    ]

    return {
        "vocabulary": vocabulary,
        "one_hot": one_hot,
        "bag_of_words": bag_of_words,
        "tf_idf": tf_idf,
    }
