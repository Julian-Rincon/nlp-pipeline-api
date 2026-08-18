"""
Pipeline compartido de spaCy — usado tal cual por las dos APIs (EC2/Cloud9 y Lambda)
para garantizar que ambas sigan exactamente el mismo flujo:
Raw text -> Preprocessing -> Feature Extraction -> Model/Analysis -> Output.
"""
import html
import re
from functools import lru_cache

import spacy
from spacy.language import Language

_REPEAT_RE = re.compile(r"(.)\1{4,}")


def _sanitize(text: str) -> str:
    """Colapsa repeticiones excesivas de un mismo carácter a un máximo de 3.
    Sin esto, el tokenizador de spaCy se vuelve casi cuadrático ante basura
    adversarial (miles de signos repetidos) — vector de bloqueo real detectado en QA."""
    return _REPEAT_RE.sub(lambda m: m.group(1) * 3, text)


@lru_cache(maxsize=1)
def get_nlp(model: str = "es_core_news_sm") -> Language:
    """Pipeline completo (incluye parser y ner) — para /dependency, /ner, /full."""
    return spacy.load(model)


@lru_cache(maxsize=1)
def get_nlp_light(model: str = "es_core_news_sm") -> Language:
    """Sin parser/ner — para /processed y /encoding, más liviano en RAM/CPU."""
    return spacy.load(model, exclude=["parser", "ner"])


# ---------------------------------------------------------------------------
# /processed — Preprocessing: limpieza + transformación (minúsculas, sin
# stopwords/puntuación, verbos lematizados). Igual a lo visto en clase.
# ---------------------------------------------------------------------------
def clean_and_transform(text: str, model: str = "es_core_news_sm") -> str:
    doc = get_nlp_light(model)(_sanitize(text))
    tokens = []
    for t in doc:
        if t.is_stop or t.is_punct or t.is_space:
            continue
        tokens.append(t.lemma_.lower() if t.pos_ == "VERB" else t.text.lower())
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# /dependency — árbol de dependencias, visualizable en HTML (displacy "dep")
# ---------------------------------------------------------------------------
def dependency_html(text: str, model: str = "es_core_news_sm") -> str:
    from spacy import displacy

    doc = get_nlp(model)(_sanitize(text))
    svg = displacy.render(doc, style="dep", jupyter=False, options={"distance": 110, "compact": True})
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Árbol de dependencias</title></head>
<body style="font-family:sans-serif;padding:24px">
<h2>Árbol de dependencias</h2>
<p><b>Texto:</b> {html.escape(text)}</p>
<div style="overflow-x:auto">{svg}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# /ner — entidades nombradas, visualizables en HTML (displacy "ent") + lista
# ---------------------------------------------------------------------------
def ner_entities(text: str, model: str = "es_core_news_sm") -> list[dict]:
    doc = get_nlp(model)(_sanitize(text))
    return [
        {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in doc.ents
    ]


def ner_html(text: str, model: str = "es_core_news_sm") -> str:
    from spacy import displacy

    doc = get_nlp(model)(_sanitize(text))
    highlighted = displacy.render(doc, style="ent", jupyter=False)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Entidades (NER)</title></head>
<body style="font-family:sans-serif;padding:24px">
<h2>Entidades nombradas</h2>
<div>{highlighted}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# /full — pipeline completo en un solo llamado: tokens+POS+lemma, texto
# preprocesado y entidades. El "flujo del pipeline" de punta a punta.
# ---------------------------------------------------------------------------
def full_pipeline(text: str, model: str = "es_core_news_sm") -> dict:
    doc = get_nlp(model)(_sanitize(text))
    tokens = [
        {"text": t.text, "lemma": t.lemma_, "pos": t.pos_, "is_stop": t.is_stop, "is_punct": t.is_punct}
        for t in doc
    ]
    entities = [
        {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in doc.ents
    ]
    return {
        "original": text,
        "processed": clean_and_transform(text, model),
        "tokens": tokens,
        "entities": entities,
    }


# ---------------------------------------------------------------------------
# /encoding — Feature Extraction: One-hot, Bag-of-Words o TF-IDF sobre el
# texto ya preprocesado, con scikit-learn (como marca el workflow del curso).
# ---------------------------------------------------------------------------
def encode_corpus(texts: list[str], model: str = "es_core_news_sm", method: str = "bow") -> dict:
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

    preprocessed = [clean_and_transform(t, model) for t in texts]

    if method == "tfidf":
        vectorizer = TfidfVectorizer()
    elif method == "onehot":
        vectorizer = CountVectorizer(binary=True)
    else:
        vectorizer = CountVectorizer()

    matrix = vectorizer.fit_transform(preprocessed)
    return {
        "method": method,
        "vocabulary": vectorizer.get_feature_names_out().tolist(),
        "vectors": matrix.toarray().tolist(),
        "preprocessed_texts": preprocessed,
    }
