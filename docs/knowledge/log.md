# Historial del conocimiento

## 2026-11-15

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
