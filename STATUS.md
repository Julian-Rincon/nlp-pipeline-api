# Estado del despliegue EC2

- **API en vivo:** http://100.30.122.233:8000
- **IP elástica desde:** 2026-09-14 (asociada a `i-0850be25ac60ca18e`, `eipalloc-0732d66059bbabdb0`), tercera cuenta de AWS Academy (`170100747321`). Las dos cuentas anteriores fueron desactivadas por Vocareum (`voc-cancel-cred`, código `SUSPENDED9` — límite de concurrencia de SageMaker por tener 5 Notebook Instances simultáneas; confirmado por el profesor, ver `Actividad 2/README.md`). El profesor asignó esta cuenta nueva de forma individual (no es la cuenta compartida del equipo) tras confirmar la causa.
- **Esta cuenta no tiene Cloud9 habilitado** — la instancia se lanzó directamente vía EC2 (AMI Ubuntu 22.04), no vía Cloud9. El requisito de la guía es la instancia EC2 en sí, no el editor Cloud9.
- **Importante — la IP es fija, pero la instancia no está garantizada 24/7:** AWS Academy Learner Lab puede detener la instancia por inactividad. Si la API no responde en esta IP, hay que arrancarla de nuevo (`aws ec2 start-instances`) dentro de una sesión activa de Academy.
- **Recomendación:** para la calificación real, usar preferentemente **Lambda Function URL o API Gateway** (ver README) — no dependen de que esta instancia EC2 esté encendida en ese momento.
- Verificado 2026-09-14: `pytest` (35/35), `qa_test.py` y `stress_test.py` (30/30 concurrentes, <10s) pasan en las 3 URLs (EC2, Function URL, API Gateway).
