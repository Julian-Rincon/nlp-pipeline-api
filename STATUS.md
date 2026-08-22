# Estado del despliegue EC2 / Cloud9

- **API en vivo:** http://23.22.176.73:8000
- **IP elástica desde:** 2026-08-22 (asociada a `i-0d14d6093d48cb5ed`, `eipalloc-07b209168580aa221`). Ya **no cambia** entre reinicios de sesión de AWS Academy — es la misma IP siempre, tal como el profesor autorizó y pidió para que su agente de calificación pueda apuntar a una URL fija.
- **Importante — la IP es fija, pero la instancia no está garantizada 24/7:** AWS Academy Learner Lab detiene la instancia EC2 automáticamente cuando detecta inactividad (observado: se apagó sola ~35 min después de arrancar, sin que nadie ejecutara `StopInstances`, incluso con tráfico HTTP real llegando a la API — Academy no lo cuenta como "actividad"). Si la API no responde en esta IP, la instancia probablemente está detenida; hay que arrancarla de nuevo (`aws ec2 start-instances`) dentro de una sesión activa de Academy.
- **Recomendación:** para la calificación real, usar preferentemente **Lambda Function URL o API Gateway** (ver README) — no dependen de que esta instancia EC2 esté encendida en ese momento. Esta IP fija es un respaldo adicional, no reemplaza la necesidad de verificar que la instancia esté corriendo justo antes de la clase del martes.
- `report-ip.service` se deja activo por si la asociación de la IP elástica cambiara alguna vez (no debería), como red de seguridad.
