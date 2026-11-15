# Contratos del núcleo (versión 1)

Python >=3.11; `media_library` 0.1.0. No hay migración implícita de estado:
`Manifest.from_dict` rechaza cualquier `schema_version` distinta de 1. Conservar
el estado original y usar una migración explícita si cambia el esquema.

`StageResult` recibe un `State`, operaciones propuestas, incidencias (`code`,
`message`, `path`, `file_id`) y evidencia JSON. Una etapa con incidencias no puede
declararse `COMPLETED`. Los estados son `PLANNED`, `RUNNING`, `WAITING_USER`,
`FAILED` y `COMPLETED`. El futuro orquestador consumirá estos contratos.

El manifiesto contiene `schema_version`, `run_id`, `config` efectiva, `versions`,
`state`, `entries`, `operations`, `events` y `sequence`. Cada entrada conserva
ID propio, rutas original/actual/relativa, stat, clasificación, información del
medio, SHA-256 calculado al planificar una mutación, decisión temporal y IDs de
operaciones. Dos archivos con los mismos bytes siguen siendo entradas distintas.

Una operación conserva ID, archivo, tipo, rutas, huella prevista, candidato,
SHA-256 de salida, backup, temporal local, estado, evidencia y error. Las fechas
y su autoridad no se deducen aquí: `temporal_decision` queda vacía hasta que una
etapa especializada la determine con fuente y zona explícitas.

La configuración TOML solo admite las tablas del ejemplo. Las herramientas se
consultan con argumentos de versión/ayuda de solo lectura; la configuración es
local y de confianza. Las estimaciones del preflight se suman por volumen y las
copias vuelven a comprobar espacio antes de escribir. El preflight no crea
destinos. El núcleo no ofrece todavía `media_library run`, etapas EXIF, vídeo,
exportación integral ni entrega remota.
