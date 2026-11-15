# Contratos del núcleo (versión 1)

Python >=3.11; `media_library` 0.1.0. No hay migración implícita de estado:
`Manifest.from_dict` rechaza cualquier `schema_version` distinta de 1. Conservar
el estado original y usar una migración explícita si cambia el esquema.

`StageResult` recibe un `State`, operaciones propuestas, incidencias (`code`,
`message`, `path`, `file_id`) y evidencia JSON. Una etapa con incidencias no puede
declararse `COMPLETED`. Los estados son `PLANNED`, `RUNNING`, `WAITING_USER`,
`FAILED` y `COMPLETED`. El orquestador de resumable-pipeline consume estos contratos.

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
destinos. `media_library run` ya orquesta etapas sobre el núcleo; los servicios
EXIF, vídeo, exportación integral y entrega remota siguen pendientes. La tabla
opcional `pipeline` congela alcance/modos; sin ella se conserva la representación
de configuración de los manifiestos anteriores.

## Estado, bloqueo y publicación

Adquirir `SourceLock(config.source)` antes de crear/cargar `RunStore`. El bloqueo
usa `flock` y un registro privado por usuario/origen resuelto en el temporal del
sistema, independiente del workspace. Un proceso activo nunca se desplaza. Tras
una salida abrupta, revisar el propietario y usar `recover_stale=True`; no borrar
el archivo de bloqueo. Al salir normalmente se vacía su propietario y se libera
el descriptor. Se requiere un sistema Unix local que soporte `flock` y hardlinks;
no es un bloqueo distribuido entre máquinas.

`RunStore.create(config, lock, entries)` realiza preflight y crea
`workspace/run_id/manifest.json` y `journal.jsonl`. Cada transición añade un
registro con secuencia, evento, estado y operación completa al journal y lo
sincroniza **antes** del snapshot atómico. Si falla la persistencia, el almacén
queda inutilizable hasta cerrar/cargar. `RunStore.load` rechaza configuración
distinta, versiones desconocidas y journals discontinuos o corruptos; reproduce
registros posteriores al snapshot y descarta solo una última línea incompleta.
`readable_log()` es una vista del registro, no una segunda fuente de verdad.

`SafeExecutor.prepare(file_id, producer, validator)` registra la intención y
asigna un candidato exclusivo bajo `workspace/run_id/file_id/`. `producer`
devuelve `ProcessResult` o `None` para escritores Python; el validador debe
rechazar contenido inválido mediante excepción y devolver evidencia JSON no vacía.
Los errores de proceso conservan su diagnóstico y cualquier parcial sin publicar.
`Artifact` acredita ruta, SHA-256 y evidencia; `plan` vuelve a verificarlo.

`plan(file_id, kind, artifact=..., destination=...)` admite:

- `replace`: sustituir exclusivamente la entrada prevista por un candidato.
- `rename`: publicar en una ruta libre del origen y retirar la ruta anterior.
- `export`: publicar una copia nueva en la raíz de exportación, sin backup de una
  entrada que no se modifica. No constituye la etapa de exportación de medios.

Se persiste la huella antes de mutar. `execute(operation_id)` crea y verifica el
backup para replace/rename, prepara una copia en el volumen del destino, vuelve
a comprobar origen/backup y publica. Los destinos nuevos se publican mediante
hardlink exclusivo; `replace` usa sustitución atómica local de la entrada cuya
huella acaba de comprobarse. No se presupone atomicidad entre volúmenes. Las
copias conservan bytes, modo y tiempos de acceso/modificación; el hash no acredita
ACL, atributos extendidos ni resource forks. Los IDs y el historial se conservan
tras renombrar. La primera copia original queda en `archive/run_id/ruta-original`;
mutaciones posteriores de esa entrada usan
`archive/run_id/.operations/operation_id/ruta-original`, sin sustituirla.

Estados por operación: `PLANNED`, `STARTED`, `BACKED_UP`, `PUBLISHING`,
`PUBLISHED`, `COMPLETED`, `FAILED`, `RESTORING`, `RESTORED`. Una operación
completada no completa toda la ejecución: el orquestador decide el estado
global. Errores operativos devuelven `StageResult(FAILED)` con diagnóstico;
conflictos de planificación/recuperación y persistencia incierta lanzan errores
tipados para impedir que el llamador continúe accidentalmente.

`inspect(id)` no modifica medios: compara entrada, candidato, salida y backup y
devuelve acciones permitidas. `execute(id)` continúa y confirma publicaciones ya
acreditadas sin repetir la transformación. `restore(id)` exige elección explícita
y backup íntegro; conserva también una salida publicada antes de restaurar.
Un contenido externo desconocido requiere nuevo plan. La restauración también
queda registrada y es recuperable. Los temporales/candidatos se conservan para
revisión; no hay limpieza ni retención automática en esta entrega.

Las equivalencias Unicode NFD y casefold se tratan conservadoramente como
colisiones incluso en volúmenes sensibles. Las colisiones entre rutas originales
se reportan antes de mutar: no se cambia silenciosamente la jerarquía del archivo.
Los symlinks a medios/directorios se reportan y no se siguen. Evitar otros
escritores (editores o sincronizadores) mientras se aplican operaciones: el bloqueo
coordina este programa, y la biblioteca estándar no ofrece un compare-and-swap
de archivos frente a escritores externos entre la última comprobación y replace.

Los `_full_path.txt` antiguos aparecen como pendientes/no soportados en el
inventario; nunca se importan como órdenes de movimiento ni se llama a
`move-biggest-videos.main()` desde el núcleo.

El pipeline persiste su propio estado versión 1 dentro de los eventos
`pipeline_checkpoint`. El journal admite un campo opcional `entries` para guardar
el inventario posterior a la revisión de importación; su replay es atómico con
el checkpoint. Se mantienen esquema del manifiesto y compatibilidad con registros
anteriores sin ese campo. Véase el [contrato de adaptadores](pipeline-adapters.md).
