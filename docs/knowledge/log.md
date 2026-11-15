# Historial del conocimiento

## 2026-11-15

- **Vídeo implementado y verificable**: Normalización MP4 por remux o recodificación combinada, perfil reproducible, geometría visual con SAR/rotación, PFR/CFR, fechas comunes y validación técnica real. Sustitución con archivo íntegro y publicación exclusiva, pausas/manual, reanudación y limpieza por operación completa.
- **Evidencia de vídeo**: 173 pruebas rápidas y 45 integraciones reales pasadas sin omisiones; 25 nuevas de vídeo con medios sintéticos. Ocho interrupciones entre volumen local y HFS+ sintético, sin recodificar ni perder originales. Wheel con preset incluido comprobado desde fuera del repositorio.
- **Límites comprobados**: Vídeo 10/11 tareas; revisión visual 3.4 pendiente y RF 22 aún propuesto. Metadata 3.3 sigue pendiente; no se afirma equivalencia con Apple Photos Brute Force. AAC de FFmpeg probado; ca_aac de Apple falló en este host. HDR/pistas avanzadas y exportación/entrega conservan sus pendientes. Ningún cambio archivado ni biblioteca personal utilizada; commits con push tras cada uno.

- **Implementación verificable de metadata-and-naming**: CaptureDate, comparación por precisión/offset/zona/DST, decisiones persistentes, lectura y escritura selectiva con ExifTool, renombrados por lote recuperables y validadores reales en metadata. Reutilizados backups, bloqueo, manifiesto y journal; las otras propuestas siguen pendientes, sin archivar cambios.
- **Evidencia real de fechas y nombres**: 139 pruebas rápidas y 20 integraciones pasadas, incluidas 18 nuevas con ExifTool 13.40 y medios sintéticos. Ambas direcciones, contenido/metadatos ajenos, atributos macOS, ciclos, idempotencia e interrupciones; 97 pruebas rápidas previas siguen pasando.
- **Documentación y límite humano**: Añadida ficha de fechas/nombres y actualizados uso, requisitos, contratos y OKF. 10/11 tareas verificadas; 3.3 Attributes/Rename/Apple Photos pendiente con protocolo de ensayo. No se ha usado biblioteca personal ni hecho cargas remotas. Commits pequeños con push tras cada uno.

- **Implementación**: Completado `resumable-pipeline`, sin archivar: comando run, alcance, planificación/aprobación, copias y pausas por ID, validación, reanudación e informes sobre el núcleo existente.
- **Verificación del proceso**: 97 pruebas rápidas pasadas (60 existentes y 37 nuevas), más las 2 integraciones reales del núcleo. Señales reales, EOF/no TTY, fallos de persistencia y recuperación sin repetir productores; recorrido completo con servicios simulados e instalación segura real.
- **Límites de integración**: EXIF, normalización, compresión, exportación y auditoría permanecen sin validador de producción; los adaptadores simulados solo se inyectan en tests. Actualizadas instrucciones y contratos, sin empezar las otras propuestas ni archivar cambios.

- **Implementación**: Completado `safe-execution-core`, sin archivar: paquete, TOML, inventario, contratos, procesos, manifiesto, journal, bloqueo, backups y recuperación por evidencia.
- **Verificación**: 60 pruebas rápidas y 2 integraciones reales con FFmpeg/ffprobe 9.0.2 y HandBrake 1.11.2 sobre fixtures sintéticos; fallos de disco/proceso/persistencia, colisiones e interrupciones cubiertos.
- **Documentación**: Añadida ficha del núcleo y contrato del esquema 1; actualizadas instalación, política y notas de los adaptadores históricos. Commits descriptivos y push a `changes-by-codex` tras cada commit.

## 2026-11-14

- **Planificación**: Añadida la política de tests automatizados solicitada por el usuario e incorporada a las reglas de OpenSpec.

## 2026-11-13

- **Limpieza**: Retirados los archivos fuera del flujo habitual y sus referencias; ajustados alcance, documentación y propuestas de implementación.

- **Verificación**: Cinco propuestas válidas con OpenSpec 2.0.0 en modo estricto; comprobados frontmatter y enlaces locales; scripts conservados sin cambios.
- **Revisión**: Aclarada la independencia del orquestador y la recuperación de una carga cuyo resultado remoto se desconoce.
- **Planificación**: Redactadas cinco propuestas OpenSpec con escenarios y tareas pendientes; añadida guía de agentes y skills evaluadas.
- **Planificación**: Inicializado OpenSpec 2.0.0 sin instalar skills; definido el comando único y cinco entregas dependientes.
- **Creación**: Transcritas las tres capturas; propuestas equivalencias CLI y documentadas las decisiones sobre resolución vertical y FPS.
- **Creación**: Documentados selección/sustitución de vídeos y exportación; completada la lectura de todos los scripts.
- **Creación**: Documentados el flujo manual y la auditoría de nombres y fechas, con tres comprobaciones sintéticas.
- **Creación**: Iniciado el paquete OKF v0.2 con [alcance y procedencia](alcance.md), basado en el commit `bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c`.
