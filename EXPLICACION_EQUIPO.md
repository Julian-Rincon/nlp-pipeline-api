# Cómo quedó el laboratorio — para explicarle al equipo

Documento interno, no es parte de la entrega. Es para que Julián lo revise y
luego se lo explique a Andrés, Juan y Miguel: qué se construyó, cómo, y por
qué quedó así.

## 1. Qué pide el laboratorio (resumen)

El profesor entregó un PDF (`Importante/Procesamiento_de_texto_con_spaCy_y_AWS.pdf`)
con un contrato **exacto** de API que evalúa con pruebas automatizadas de caja
negra contra dos despliegues en vivo (EC2 y Lambda). No es "hagan algo que
procese texto" — es "expongan exactamente estas 5 rutas, con esta forma de
entrada/salida, con estas reglas de validación, en estas dos arquitecturas de
AWS, con estos límites de rendimiento y concurrencia".

Pesos de calificación (según el propio PDF):

| Sección | Peso |
|---|---|
| Vectorización | 20% |
| Paridad entre despliegues (EC2 vs Lambda) | 15% |
| POS y lematización | 10% |
| Reconocimiento de entidades (NER) | 10% |
| Contrato y validación | 10% |
| Robustez y consistencia | 10% |
| Concurrencia y rendimiento | 10% |
| Limpieza de texto | 8% |
| Visualización de dependencias | 7% |

## 2. Qué construimos

**Un solo código, dos despliegues.** Toda la lógica de PLN vive en dos
archivos compartidos (`nlp_pipeline.py` y `main.py`) que corren tal cual en
ambas arquitecturas — así garantizamos que EC2 y Lambda respondan exactamente
lo mismo (la "paridad" que pesa 15%).

```
aws_apis/
  nlp_pipeline.py   # limpieza, POS, NER, dependencias, vectorización
  main.py           # la app FastAPI con las 5 rutas del contrato
  ec2/              # solo lo específico de EC2 (systemd, script de IP)
  lambda/           # solo lo específico de Lambda (Dockerfile, handler)
  tests/            # 35 pruebas automáticas
  qa_test.py, stress_test.py   # pruebas de carga/estrés contra las URLs reales
```

**Las 5 rutas exigidas:**

| Ruta | Qué hace |
|---|---|
| `POST /api/v1/clean` | Limpieza: minúsculas, sin puntuación ni stopwords |
| `POST /api/v1/pos` | Tokens + categoría gramatical + lema |
| `POST /api/v1/ner` | Entidades nombradas (persona, lugar, organización...) |
| `POST /api/v1/visualize/dep` | Árbol de dependencias sintácticas (HTML con SVG) |
| `POST /api/v1/vectorize` | Bag-of-Words, One-Hot y TF-IDF sobre varios documentos |

**Los dos despliegues en vivo:**

- **EC2 / Cloud9**, corriendo con `systemd` (se reinicia solo si el proceso
  muere) — IP fija `23.22.176.73` (ver sección 5).
- **AWS Lambda**, como imagen de contenedor, expuesta por **Function URL**
  (tal como pide la guía) y también por API Gateway como respaldo adicional.

## 3. Decisiones técnicas que vale la pena poder explicar

- **Vectorización hecha a mano, sin scikit-learn.** La guía pide una forma muy
  específica de TF-IDF (sin normalizar, fórmula exacta) y de One-Hot (una
  matriz por documento, una fila por cada palabra que aparece — no un vector
  por documento). Eso no es lo que entrega scikit-learn por defecto, así que
  lo implementamos en Python puro. De paso, evitó problemas de compatibilidad
  al construir la imagen de Lambda.
- **Tres variantes del modelo de spaCy** (`get_nlp_light`, `get_nlp_ner`,
  `get_nlp_dep`), cada una cargando solo las piezas que necesita (por ejemplo,
  `/clean` no necesita el analizador de entidades). Esto es lo que nos
  mantiene muy por debajo del límite de 10 segundos por solicitud que exige
  la guía.
- **Protección contra texto adversarial**: si alguien manda miles de
  caracteres repetidos (`"aaaaaaaaa...miles de veces"`), el tokenizador de
  spaCy se vuelve muy lento. Lo detectamos en pruebas de estrés y lo
  arreglamos colapsando repeticiones largas antes de procesar.
- **Validación "todo o nada"**: si mandas un lote de 10 textos y uno solo
  viene mal (vacío, tipo incorrecto, etc.), la API rechaza el lote completo
  con error — nunca devuelve resultados parciales. Es lo que exige la guía.

## 4. Un bug real que encontramos (y cómo lo encontramos)

Antes de entregar, hicimos algo que vale la pena contarle al equipo: creamos
un **agente evaluador independiente**, cuyo único contexto era el PDF del
profesor (no sabía nada de nuestras decisiones ni del código), y lo pusimos a
probar las dos APIs en vivo como si fuera el sistema automático de
calificación del profesor.

Encontró que la puntuación pegada a una palabra (`"casa.perro"`,
`"casa;perro"`, `"casa-perro"`, etc.) no se estaba separando correctamente —
solo la coma y los dos puntos funcionaban bien. El resto quedaba pegado,
contaminando tanto `/clean` como el vocabulario de `/vectorize` (28% del peso
total entre las dos secciones). Era un defecto real del tokenizador de
spaCy, no algo que hubiéramos probado a fondo antes.

Lo arreglamos (ya no depende del comportamiento interno de spaCy para
separar puntuación) y volvimos a correr el mismo agente evaluador: la segunda
vez calificó **5.0 / 5.0**, con las 9 dimensiones en verde.

Esto es útil para contarle al equipo porque es evidencia concreta de que se
probó adversarialmente antes de entregar, no solo "correlo y ya sirvió".

## 5. Un detalle de infraestructura que hay que tener presente

AWS Academy (la cuenta de laboratorio que usamos) apaga la instancia de EC2
sola después de un rato de inactividad — lo confirmamos, no es que nosotros
la apaguemos ni que se acabe la sesión de 4 horas. Por eso:

- Le pedimos al profesor autorización para usar una **IP elástica** (fija) en
  la instancia de EC2, para que su sistema de calificación siempre encuentre
  la misma URL — ya está configurada (`23.22.176.73`).
- Pero la IP fija no garantiza que la instancia esté **prendida** en el
  momento exacto de la calificación. Por eso la recomendación real es que el
  profesor use preferentemente **Lambda Function URL o API Gateway**, que no
  dependen de que alguien haya encendido la instancia de EC2 antes.
- Antes de la clase del martes, hay que entrar y confirmar que las tres URLs
  respondan (toma un par de minutos).

## 6. URLs vigentes ahora mismo

| Despliegue | URL |
|---|---|
| EC2 (IP fija) | `http://23.22.176.73:8000` |
| Lambda Function URL | `https://7jh7mtmt7a54pg7xqpnjdxf2tu0kuyia.lambda-url.us-east-1.on.aws` |
| API Gateway (respaldo) | `https://u04py63z34.execute-api.us-east-1.amazonaws.com` |

## 7. Cómo se verificó todo

- 35 pruebas automáticas (`tests/test_api.py`) que cubren cada ruta y cada
  regla de validación de la guía.
- Pruebas de carga (`stress_test.py`): 25 documentos de ~1000 caracteres,
  30 solicitudes simultáneas — todo por debajo del límite de 10s.
- Comparación directa EC2 vs Lambda con las mismas solicitudes: respuestas
  idénticas.
- El agente evaluador independiente (sección 4), corrido dos veces.

## 8. Sobre el uso de IA (para que el equipo lo tenga claro)

La guía del profesor permite explícitamente el uso de herramientas de IA y
pide declararlo (ya está en el README del repo, sección "Uso de inteligencia
artificial generativa"). Se usó Claude Code durante todo el desarrollo:
diseño, implementación, despliegue en AWS, y las pruebas/depuración
descritas arriba. El equipo revisó el código antes de cada entrega.
