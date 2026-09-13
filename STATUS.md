# Estado del despliegue EC2

- **API en vivo:** http://44.198.226.249:8000
- **IP elástica desde:** 2026-09-12 (asociada a `i-096486a3f824518c3`, `eipalloc-05f07bc7bc377f1d0`), cuenta de AWS Academy nueva (la anterior fue desactivada por Vocareum — código `SUSPENDED9`, límite de concurrencia de SageMaker, ver `Actividad 2/README.md`).
- **Esta cuenta no tiene Cloud9 habilitado** — la instancia se lanzó directamente vía EC2 (AMI Ubuntu 22.04), no vía Cloud9. El requisito de la guía es la instancia EC2 en sí, no el editor Cloud9.
- **Importante — la IP es fija, pero la instancia no está garantizada 24/7:** AWS Academy Learner Lab puede detener la instancia por inactividad. Si la API no responde en esta IP, hay que arrancarla de nuevo (`aws ec2 start-instances`) dentro de una sesión activa de Academy.
- **Recomendación:** para la calificación real, usar preferentemente **Lambda Function URL o API Gateway** (ver README) — no dependen de que esta instancia EC2 esté encendida en ese momento.
- `report-ip.service` se deja activo como red de seguridad.
