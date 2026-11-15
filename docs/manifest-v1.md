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
y su autoridad no se deducen en el núcleo: el servicio de metadata ya completa
`temporal_decision` con auditoría, fuente, precisión, zona/offset y decisiones
explícitas. Se persiste como snapshot de entradas en el journal.

La configuración TOML solo admite las tablas del ejemplo. Las herramientas se
consultan con argumentos de versión/ayuda de solo lectura; la configuración es
local y de confianza. Las estimaciones del preflight se suman por volumen y las
copias vuelven a comprobar espacio antes de escribir. El preflight no crea
destinos. `media_library run` ya orquesta etapas sobre el núcleo; los servicios
EXIF/QuickTime, vídeo, exportación y auditoría tienen servicios reales. La entrega
usa un protocolo de cliente con transporte simulado en pruebas y compatibilidad
específica de gphotos pendiente. La tabla
opcional `pipeline` congela alcance/modos; sin ella se conserva la representación
de configuración de los manifiestos anteriores. `[dates]` también es opcional y
se omite de la representación efectiva cuando está vacía; una vez configurada
queda congelada, con excepciones por ruta original de entrada.
`[video]` es opcional con la misma compatibilidad de omisión; conserva selección,
perfil, ahorro, migración histórica y revisión visual declarada. El antiguo texto
`pipeline.compression_profile` sigue siendo descriptivo para adaptadores externos;
el servicio real obtiene sus opciones de `[video]`.

## Estado, bloqueo y publicación

Adquirir `SourceLock(config.source)` antes de crear/cargar `RunStore`. El bloqueo
usa `flock` y un registro privado por usuario/dispositivo/inode en el temporal del
sistema, independiente del workspace. Un descriptor del origen y comprobaciones
de identidad detectan sustituciones del directorio. Los alias admitidos comparten
el bloqueo; también se adquiere el lock anterior por ruta para conservar su
propietario activo/obsoleto. Un proceso activo nunca se desplaza. Tras
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
- `substitute`: publicar un Artifact transformado en una ruta libre del origen
  y retirar la entrada anterior solo después de verificar publicación y backup.
  Usado por vídeo; conserva identidad y ruta original, con `source_retired`
  registrado antes de completar. Colisiones fallidas no acreditan propiedad de
  una salida existente aunque sus bytes coincidan.

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
Los objetivos de FileModifyDate/FileCreateDate solicitados por metadata viajan
en la evidencia, se reaplican al temporal local de publicación y se verifican
en la ruta final. La creación requiere macOS/birthtime/SetFile y precisión de
segundos; no amplía la garantía a todos los atributos del filesystem.

`evidence.publication_identity` conserva dispositivo/inode del temporal local en
publish_intent, antes de link/replace. La recuperación pendiente exige esa identidad
en destino y hash correcto, o un hardlink local propio en estados anteriores.
`publication_rejected` se conserva también para rename; solo una nueva intención
con temporal acreditado puede retirarlo. Sin prueba de propiedad no se adopta un
destino idéntico ni se retira el origen. Una publicación anterior sin enlace ni
identidad suficiente conserva una pausa/conflicto para revisión.

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
queda registrada y es recuperable. Se retira únicamente el enlace temporal local
propio tras verificar `PUBLISHED`, antes de capturar el stat final y registrar
`COMPLETED`: desvincularlo cambia ctime. Se exige que siga siendo el mismo archivo
publicado; si no, se informa del conflicto. Candidatos y backups se conservan
para revisión; no hay limpieza global ni política de retención automática.

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
El esquema sigue siendo 1: `substitute` es un tipo de operación nuevo y exige esta
versión del ejecutor; una versión anterior lo rechazará al intentar ejecutarlo.
Las identidades de adaptadores quedan congeladas; ejecuciones con adaptadores
anteriores no se reinterpretan automáticamente al actualizar el programa.

`export_settings` representa la tabla TOML `[export]` y `delivery` la tabla del
mismo nombre; se omiten de configuración efectiva cuando no se declararon, como
las opciones anteriores. La receta no depende del ID nuevo de inventario: enlaza
identidad lógica, procedencia, hashes, fecha, perfil y versiones. Se sigue la
cadena de operaciones/entradas previas del mismo origen y archivo, incluso al
elegir una raíz de exportación distinta.

Renovar un exportado propio conserva `evidence.previous_destination` con su stat
y hash; el backup corresponde a ese derivado anterior, no al original fuente.
`backup_hash` distingue ambas garantías. El ejecutor compara origen y destino
anterior antes de publicar, preserva la copia verificada y usa sustitución atómica
local. Un destino sin propiedad acreditada por el servicio no admite esa vía.

`coverage` y `delivery_job` viven en checkpoints del mismo journal. La entrega
numera revisiones del job cuando cambia su checkpoint. Intento/revisión y estado
permiten reconciliar todos sus antecedentes; un READY antiguo no puede ignorar
una entrega incierta posterior. Los snapshots previos sin revisión se comparan
conservadoramente por intento/progreso.
La entrega
persiste SUBMITTING antes del cliente y DELIVERED antes de copiar su estado.
Alcance/identidad/hash/alias ligan la evidencia; una entrega incierta no se repite
automáticamente, tampoco cambiando el comando desde otra ejecución. El estado
del cliente se copia a directorios privados con recibo por árbol; no se registran
sus contenidos ni stdout/stderr. Véase el [protocolo](delivery-protocol.md).
