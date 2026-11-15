---
type: Reference
title: Exportación y entrega verificables
description: Recetas, derivados, auditoría local, entrega optativa y pruebas remotas pendientes.
tags: [actual, exportacion, entrega, recetas, recuperacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: export
    resource: ../../src/media_library/export_stage.py
  - id: delivery
    resource: ../../src/media_library/delivery_stage.py
  - id: integration
    resource: ../../tests/test_delivery_pipeline_integration.py
  - id: photos-policy
    resource: https://developers.google.com/photos/support/updates
  - id: uploader
    resource: https://github.com/gphotosuploader/gphotos-uploader-cli/releases/tag/v6.0.0
  - id: uploader-scope
    resource: https://github.com/gphotosuploader/gphotos-uploader-cli/blob/v6.0.0/internal/cli/push/push.go
  - id: uploader-auth
    resource: https://github.com/gphotosuploader/gphotos-uploader-cli/blob/v6.0.0/internal/oauth/oauth.go
---
# Capacidades locales

`export`, `audit` y `delivery` ya tienen adaptadores de producción sobre el
[pipeline reanudable](pipeline-reanudable.md). Reutilizan inventario, fechas,
SafeExecutor, journal, bloqueo y los validadores/codificadores existentes. Los
scripts históricos conservan su comportamiento; no son esta entrada del servicio.
No se ha archivado ninguna propuesta.

La receta registra identidad lógica, ruta/huella de fuente, correspondencia con
la biblioteca, decisión temporal, perfil/opciones y versiones. Descubre años y
álbumes recorriendo el origen configurado, con `pipeline.include` y exclusiones.
El destino es `export/ruta-relativa-del-medio-actual.jpg|mp4`; no se aplana por
basename. Los temporales y operaciones mantienen IDs independientes.[^export]

Se sigue la procedencia entre ejecuciones, incluso tras nuevas correcciones de
metadata y al elegir otra raíz de exportación. Si hay un original archivado
registrado, se exige su hash y se usa para evitar volver a perder calidad desde
el 720p. Si falta/cambió, hay conflicto; no se sustituye silenciosamente por el
derivado. `use_archived_original=false` es una elección explícita, registrada.
El ID de inventario nuevo no cambia por sí solo la receta: la identidad lógica
y las huellas establecen la correspondencia.

# Recetas, imágenes y vídeo

```toml
[export]
images = true
videos = true
image_max_side = 1200
image_quality = 90
color_policy = "preserve-icc"
video_profile = "upload-480p30"
video_quality = 22
video_frame_rate_mode = "pfr"
video_quality_reviewed = false
require_capture_date = true
use_archived_original = true
```

JPEG RGB/L de una imagen: Pillow aplica `ImageOps.exif_transpose`, reduce sin
ampliar y normaliza Orientation=1 y dimensiones EXIF. Conserva los bytes ICC sin
convertir color ni cambiar modo. Los JPEG pequeños sin bloque EXIF funcionan;
CMYK, otros modos/formatos o conversiones de color requieren política y quedan
pendientes. No se afirma conservación universal de todos los metadatos del original.
Se restauran/releen las fechas seleccionadas con ExifTool y se valida legibilidad.

La fecha procede de las [decisiones comunes](fechas-nombres.md), incluida su zona;
no se usa mtime. Sin fecha resuelta se conserva una pausa explícita. Es posible
configurar `require_capture_date=false` para una exportación local de imagen
con fecha desconocida; el informe la identifica y la entrega sigue bloqueada si
`delivery.require_capture_date=true`. No hay KeyError por ausencia de EXIF.

Vídeo reutiliza [codificación y validación](video-validado.md), con el perfil
independiente `upload-480p30`: límites visuales 854×480 apaisado, 480×854 vertical
y 480×480 cuadrado, PFR <=30, SAR 1:1 y redondeo par con DAR <=0,5%. Admite también
los perfiles archive-720p30/height-720 y CFR explícito. Contempla rotación, no amplía
ni recorta y mantiene la ruta AAC de FFmpeg probada. Una fuente H.264/MP4 que ya
cumple el objetivo puede copiarse sin recodificar; queda registrado como `copy`.
Una receta vigente se reutiliza tras volver a pasar el validador.

Un derivado de carga puede ser mayor: no sustituye el original y no se presenta
como ahorro de la biblioteca. La revisión visual de una nueva recodificación de
carga es independiente: `video_quality_reviewed=false` permite preparar/validar y
pausa antes de publicar; `decidir export_quality_reviewed=true` y `comprobar`
registran una declaración humana. El RF 22 de carga también sigue propuesto.
No se elude la revisión anterior: una instalación 720p pendiente bloquea las
etapas posteriores de ese archivo. Los tests declaran revisiones sintéticas para
probar el protocolo; no acreditan calidad visual real.

En modo export manual se preparan copias de la fuente de mayor calidad por ID.
La salida debe estar en su directorio propio; `decidir output="/ruta/a/copia"`
permite asociarla explícitamente. Se valida con los mismos lectores, se aplica la
decisión temporal persistente y no se publica por confirmar sin una salida válida.

# Vigencia y auditoría global

La presencia del destino no acredita nada por sí sola. Solo se reutiliza una
publicación registrada de la misma identidad, receta/huellas y resultado íntegro
que vuelva a superar el validador. Un destino ajeno abre conflicto. Cambiar perfil,
fecha, fuente, opciones o versiones cambia la receta. Un derivado propio inválido
o desactualizado se conserva en archivo antes de renovarlo, con huellas del
destino anterior y candidato acreditado; los cambios externos detienen la operación.
La recuperación puede reutilizar el candidato sin volver a renderizar/codificar.

`coverage` muestra exportados, exclusiones con motivo y pendientes/errores por
archivo. La auditoría revalida receta, legibilidad/decodificación, dimensiones,
orientación, color/fechas y correspondencia. Un archivo elegible sin derivado
impide entregar **todo ese alcance**; no basta que otro haya terminado. La entrega
vuelve a comprobar los derivados y usa copias exclusivamente de los exportados
auditados en un `scope.json` privado, nunca el archivo de originales.

# Entrega optativa y evidencia

Configurar `pipeline.modes.delivery="disabled"` y `[delivery] mode="disabled"`
completa solo alcance local y no invoca clientes. Para manual, ambos modos son
`manual`: se muestra el manifiesto de alcance y solo después de la acción externa
se declara `decidir delivery_confirmed=true`, seguido de `comprobar`. EOF no declara
entrega. La declaración humana no prueba presencia remota ni consulta APIs.

`configured-cli` requiere `pipeline.modes.delivery="auto"`, opt-in `allow_cli=true`,
alias de destino no secreto, ejecutable/argumentos y preflight explícitos. Está
implementado el [protocolo de cliente con alcance limitado](../delivery-protocol.md).
El cliente debe aceptar exactamente el manifiesto y acreditar capacidad y
autenticación para ese alias. En esta sesión solo se ha probado con un proceso
Python local **simulado**, sin sockets, cuentas ni cargas. El protocolo no convierte
automáticamente un uploader arbitrario en un adaptador compatible.

| Evidencia | Qué acredita |
| --- | --- |
| Validación local | Derivados vigentes e íntegros dentro del alcance. |
| Returncode cero | El comando terminó correctamente; no acredita cada medio remoto. |
| Recibos del cliente por job/ID/hash | Comprobantes aportados por el adaptador, ligados a los archivos; sin auditoría API independiente. |
| Declaración/reconciliación humana | El usuario declara haber entregado o revisado el resultado. |

`remote_presence_verified` permanece false: este cambio no implementa una consulta
remota independiente. Sin recibos completos se pide declaración humana. Tras
timeout, interrupción o error incierto no se repite automáticamente: se recuperan
recibos válidos o se declara `delivery_resolution=delivered|not-delivered` después
de revisar el cliente. `not-delivered` autoriza un intento concreto; no crea un
bucle de reintentos. Cada nueva declaración explícita de delivery_resolution se vincula al job y a su
intento incierto mediante una autorización consumible. Cambiar delivery_confirmed
o una revisión general no crea otra autorización. Las resoluciones históricas sin
vinculación deben declararse otra vez después de revisar el resultado.
Otra ejecución equivalente reutiliza la evidencia registrada. Se reconcilian
todos los antecedentes por job, incluido el propietario de un READY
antiguo al reanudarlo. Intento y revisión duradera prevalecen sobre ese snapshot;
el orden de los UUID de ejecución no acredita progreso. Sin revisión histórica,
se conserva el estado más avanzado del intento. Jobs distintos con entrega posible
para el mismo alcance requieren reconciliación.
Antes de habilitar un envío se exige historial legible y validable: se enumeran
los directorios de ejecución sin omitir errores y se contrastan snapshot,
secuencia, journal y checkpoints de entrega. Un manifiesto ausente, ilegible,
corrupto o enlazado deja `WAITING_USER` con la ruta y clase de error en el informe
y journal actual. No se puede presumir que un antecedente ilegible sea ajeno.
La exportación local puede seguir reutilizando un derivado acreditado por otro
run; esa reutilización no autoriza entregar sin conocer los demás antecedentes.

Para recuperar: restaurar permisos/acceso o una copia íntegra verificada del
estado, sin borrar el run ni inventar un estado READY. Si el snapshot quedó
atrasado respecto al journal, reanudar primero ese run con su configuración
original para recuperar sus eventos. Después reanudar la ejecución bloqueada.
El intento UNCERTAIN recuperado sigue pendiente; solo recibos o una reconciliación
explícita por job/intento permiten resolverlo. `delivery_confirmed=true` no
permite ignorar historial desconocido. El recorrido de entrega no repara ni
reescribe silenciosamente otros runs.
Cambiar el comando tampoco elude una entrega incierta al mismo alias. Alcances
solapados que no puedan reconciliarse quedan pendientes, sin duplicar cargas.[^delivery]

# Autoridad al seleccionar antecedentes

La lectura estricta de entrega recorre todos los runs del workspace. Las rutas
source/archive de una cabecera no prueban que un envío sea ajeno. La procedencia
local conserva su descubrimiento tolerante; la selección de jobs usa esta regla:

| Evidencia persistida | Qué acredita |
| --- | --- |
| `scope.files` y `payload_hash` del job | Identidades lógicas, hashes de los derivados y claves de receta del alcance. Los checkpoints se contrastan con su journal. |
| `delivery_signature` del job | Huella SHA-256 de toda la configuración efectiva de entrega: modo, alias, argumentos y opciones, incluidos defaults. No es una firma digital. |
| Intento, revisión y estado | Progreso duradero del mismo job; un READY antiguo no prevalece sobre un intento posterior incierto. |
| Autorización por job/intento y `resolution_consumed` | Permiso explícito para un único reintento. Recuperar una cabecera no lo renueva. |

Primero se acredita el alcance. Un conjunto sin ninguna pareja coincidente de
identidad lógica y hash del derivado es disjunto y puede excluirse sin consultar
un target auxiliar. Para un alcance solapado, la configuración efectiva completa
registrada debe coincidir con la huella persistida del job **antes** de usar su
target. Solo entonces un alias diferente acredita independencia dentro del
protocolo. Si falta evidencia o la configuración no concuerda, queda WAITING_USER
con ruta y motivo, antes de preflight/submit; una confirmación genérica no lo elude.

Si coinciden destino, payload y configuración, se reconcilian los snapshots por
intento/revisión/progreso como antes. Otro payload o configuración al mismo alias
con entrega posible exige reconciliación. En los contratos antiguos sin tabla
delivery explícita se reconstruyen los defaults manual/disabled que aplicaba el
servicio y también se exige la huella coincidente; no se migra el estado en silencio.
El contrato serializado del job sigue siendo el mismo.

Identidad/hash distinguen versiones concretas de derivados; no implementan
deduplicación perceptual ni descubrimiento de otros workspaces. Target es un
alias lógico configurado: ni esta comparación ni el cliente simulado acreditan
que dos alias representen cuentas remotas distintas. Las huellas y el journal
no protegen contra una edición coordinada de todas las evidencias. Siguen
pendientes las pruebas remotas y los riesgos de escritores externos/alimentación.

Para recuperar incoherencias, restaurar estado auténtico desde copia fiable y
reanudar. No recalcular delivery_signature para hacer encajar una cabecera ni
borrar antecedentes. El job incierto recuperado sigue exigiendo recibos o
reconciliación explícita, y los permisos consumidos siguen consumidos.

# Backup del estado y recuperación

`state_dir` y `backup_dir` se configuran juntos, disjuntos de las cuatro raíces
operativas y entre sí. Tras acreditar la entrega se congela el inventario del
estado y se copia por hash bajo `backup_dir/run-id/job-id/files/`. Directorios
privados 0700 y archivos 0600; el recibo local registra cantidad y hash del árbol.
Los informes/journal no contienen los bytes del estado ni stdout/stderr del cliente.
No poner credenciales en TOML, argumentos o Git: el adaptador autentica externamente.

Un backup fallido deja la entrega duraderamente acreditada y la ejecución sin
completar; al reanudar se verifica/continúa solo su backup, sin volver a enviar.
El inventario propaga errores al recorrer directorios: una subcarpeta ilegible no
puede omitirse y producir un falso backup vacío/verificado. Tras recuperar acceso,
se continúa el backup. Un directorio realmente vacío y legible sí es válido.
No se sobrescriben copias parciales ajenas o cambiadas. Un estado fuente que cambió
respecto al snapshot requiere revisión. Se conserva evidencia de entregas anteriores;
no hay borrado global ni rotación de credenciales. El backup de un directorio no
acredita recuperación de secretos guardados fuera de él, por ejemplo en Keychain.

# Requisitos y tareas pendientes

Instalar `python -m pip install -e '.[dev,images]'`, ExifTool, FFmpeg/ffprobe y
HandBrakeCLI. Probados Pillow 12.3.0, ExifTool 13.40, FFmpeg/ffprobe 9.0.2 y
HandBrakeCLI 1.11.2 con Python 3.12.15. El preset JSON se distribuye con el paquete.
El uploader no se instala ni autentica como requisito del recorrido local/manual.

Se ha evaluado el código público v6.0.0 de gphotos-uploader-cli y comprobado la
misma versión instalada usando un directorio temporal vacío. Sus jobs permiten
SourceFolder e inclusiones/exclusiones y `push` recorre todos los jobs de su
configuración. La autenticación pide appendonly y scopes de datos creados por la
app. Esto permite diseñar un adaptador aislado, pero no acredita autenticación,
recibos ni limitación efectiva en una cuenta real.[^uploader][^uploader-scope][^uploader-auth]

La tarea **2.3 permanece pendiente** para el adaptador específico de gphotos y su
autenticación/compatibilidad real. No se ha ejecutado `auth`, `push` ni consultado
cuentas. No usar directamente ese binario como si hablara el protocolo genérico.
Un ensayo posterior autorizado deberá usar una cuenta/lote de prueba, configuración
aislada con un único SourceFolder apuntando a las copias del scope, sin borrado,
backend de secretos y estado identificados. Comprobar permisos, hashes/IDs enviados,
recibos, interrupción/reconciliación y recuperación del backup sin duplicados.

Desde el 31-03-2025, la API limita la lectura/gestión a datos creados por la app y
retiró los scopes amplios anteriores; appendonly sigue permitiendo añadir medios.
No se promete auditar toda la biblioteca de Google Photos con los permisos de
una aplicación.[^photos-policy]

También siguen pendientes metadata **3.3** (Attributes/Rename/Apple Photos) y vídeo
**3.4** (muestra visual RF propuesto). No se afirma equivalencia con Brute Force.
Las [pruebas y estado de las cinco propuestas](verificacion.md) distinguen estas
revisiones de la implementación y de los ensayos remotos aún no autorizados.

[^export]: [Exportador y auditor](../../src/media_library/export_stage.py).
[^delivery]: [Máquina de estados de entrega](../../src/media_library/delivery_stage.py).
[^uploader]: [Versión pública v6.0.0](https://github.com/gphotosuploader/gphotos-uploader-cli/releases/tag/v6.0.0).
[^uploader-scope]: [Recorrido de jobs de push v6.0.0](https://github.com/gphotosuploader/gphotos-uploader-cli/blob/v6.0.0/internal/cli/push/push.go).
[^uploader-auth]: [Scopes OAuth v6.0.0](https://github.com/gphotosuploader/gphotos-uploader-cli/blob/v6.0.0/internal/oauth/oauth.go).
[^photos-policy]: [Cambios oficiales de la API de Google Photos](https://developers.google.com/photos/support/updates).
