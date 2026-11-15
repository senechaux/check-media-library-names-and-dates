# Contrato de integración del pipeline

`Pipeline` consume `StageResult`, `RunStore`, su journal y `SafeExecutor` del
núcleo. Su estado propio versión 1 vive en eventos `pipeline_checkpoint`, dentro
del manifiesto/journal versión 1. El inventario posterior a la revisión de
importación se persiste mediante el campo opcional `entries` del registro de
journal; al recuperar se reproduce antes de continuar. Los manifiestos anteriores
sin `pipeline` en configuración siguen siendo compatibles con el núcleo.

## Etapas y adaptadores

Orden fijo: preflight → import_review → inventory → plan → metadata → normalize
→ compression → installation → export → audit → delivery → close. El TOML
selecciona patrones relativos (`pipeline.include`) y modos `auto`, `manual` o
`disabled`. Cada archivo solo avanza cuando sus etapas previas habilitadas están
completas; los pendientes no bloquean archivos independientes. La revisión de
importación es una barrera global humana antes del inventario.

| Servicio | Adaptador de esta entrega | Integración posterior |
| --- | --- | --- |
| Preflight/inventario/plan/estado/informe | Real, del núcleo y orquestador | — |
| Revisión de importación | Declaración humana local; ninguna sincronización | No automatiza Dropbox/Drive |
| Nombres/fechas | `MetadataAdapter` real (`metadata-and-naming:v1`), ExifTool selectivo, decisiones, validación y renombrado por lote | Ensayo humano de apps/Photos pendiente |
| Normalización de vídeo | `VideoAdapter` real: remux compatible o recodificación combinada, ffprobe/FFmpeg/ExifTool | Políticas HDR/pistas avanzadas pendientes |
| Compresión | `VideoAdapter` real: perfil reproducible, HandBrake, validación técnica, fechas y ahorro | Calidad visual requiere declaración humana |
| Instalación | `InstallationAdapter` real: candidato → replace o substitute, backup y recuperación; metadata ya aplicada no se repite; revisión visual separada para vídeo | Limpieza por operación completa |
| Exportación/auditoría | `ExportAdapter` y `AuditAdapter`: receta, fuente registrada, validación, vigencia y cobertura global | Formatos/políticas no cubiertos conservan pausa |
| Entrega | `DeliveryAdapter`: disabled/manual o protocolo CLI con opt-in, alcance, reconciliación y backup | Autenticación real de gphotos pendiente; transporte simulado en tests |

Los adaptadores simulados están **solo en tests** y se inyectan por Python con
`main(..., adapters={etapa: adaptador})` o `Pipeline(..., adapters=...)`. No hay
un flag de producción que simule éxito de EXIF, vídeo o entrega. El informe
identifica `identity`, `simulated` y confirmaciones humanas. Los adaptadores
por defecto sin validador siempre dejan la etapa pendiente, aunque se confirme.

## Interfaz para el próximo servicio

Un `Adapter` declara `identity` estable y versionada, `simulated` y `human`, y
ofrece:

- `instructions(context)`: descripción de solo lectura con herramienta, ajustes
  y evidencia esperada; se usa para mostrar el plan antes de aprobar.
- `run(context) -> StageResult`: se llama en modo automático después de aprobar.
- `validate(context) -> StageResult`: reaudita tras `comprobar` y al reanudar una
  pausa técnica. Debe ser idempotente y recuperar candidatos/operaciones ya
  preparados; nunca volver a producir o publicar trabajos acreditados.

Los hooks opcionales `preview(pipeline)` y `finalize(pipeline, recover_only=False)`
permiten reservas globales. Metadata presenta auditorías y destinos del lote antes
de aprobar; su finalización usa `RenameBatch` para evacuar nombres por ID y publicar
destinos mediante operaciones seguras. El lote completo y cada paso se registran
en el journal. `recover_only=True` recupera un lote interrumpido antes de comparar
las rutas de origen, que pueden estar en sus temporales propios. Una reserva
pendiente impide declarar completada la ejecución. Los demás adaptadores no
necesitan estos hooks.

`StageContext` expone etapa, ID, entrada, registro, pausa, decisiones, almacén y
ejecutor. `artifact()` encuentra el último candidato de las etapas precedentes.
Una etapa que prepara contenido devuelve `evidence['artifact'] = asdict(Artifact)`
obtenido con `context.executor.prepare(context.file_id, producer, validator)`.
Su validador debe lanzar una excepción si el contenido
no es válido. La evidencia no vacía documenta qué se comprobó, sin convertir
una confirmación en comprobación técnica.

Las mutaciones de originales se devuelven como operaciones **planificadas** en
`StageResult.operations`; el adaptador no llama a `execute`, no modifica
originales ni usa `main()` históricos. El orquestador guarda el resultado validado
y los IDs antes de ejecutar operaciones; solo registra la etapa completada al
acreditar todas sus publicaciones. Si la interrupción sucede entre planificar y
guardar el resultado, entrega los IDs recuperados a `validate`: no presume que
la etapa estuviera validada. InstallationAdapter resuelve ese caso comprobando
el candidato previo. Un adaptador sin validador mantiene el trabajo pendiente.
La finalización de renombrado es una operación global del servicio, registrada
mediante `RenameBatch` y ejecutada con `SafeExecutor`, para permitir ciclos. En la
revalidación de operaciones antiguas, una salida consumida por un renombrado
posterior de la misma entrada no se considera perdida; se verifica el destino
final y los backups. Los checkpoints se copian al replay para no alterar eventos
históricos al actualizar el estado actual.

Usar `WAITING_USER` para evidencia ausente/conflictos que requieren decisión y
`FAILED` para fallo operativo con diagnóstico. `COMPLETED` requiere evidencia,
sin incidencias. Una etapa sin cambio puede acreditar `{'unchanged': True, ...}`.
Las identidades y toda la configuración efectiva se congelan; un cambio exige
nueva planificación. La auditoría local final ahora es real y su cobertura global
debe estar completa antes de iniciar entrega.

## Trabajo externo y asociación

La pausa guarda ID, etapa, archivos, entradas/salidas, herramienta, ajustes,
evidencia requerida, decisiones y condición de continuación. Para Attributes,
Rename, conversión, HandBrake y exportación se preparan copias bajo
`workspace/run_id/file_id/manual/etapa/`. Un renombrado posterior no provoca que
se regenere la copia de entrada ni que se sustituya por el original.

`associate_outputs` admite huella única o asociación explícita por ID. Rechaza
ambigüedad, incluso dos archivos con bytes idénticos, y rechaza compartir salida.
El consumidor limita los candidatos a sus directorios de trabajo, valida sus
rutas y consume la decisión `output` cuando el contenido ya no conserve su hash.
No se adivina por nombre/posición. `authority`, `timezone`, `fold`, `offset`,
`source_tag`, `date` y opciones de fecha se conservan como decisiones y pasan por
la validación de dominio del servicio real antes de guardarse. `output` sigue
limitado al directorio propio de trabajo. Vídeo añade historical_policy,
allow_remux_growth y quality_reviewed. Esta última es declaración humana, sin
atribuir calidad visual a la validación técnica.

`video_work` congela en el checkpoint por archivo un plan compartido por normalize
y compression, fecha/decisión, tags de origen y huella. Una sola etapa prepara el
candidato y la otra reconoce el trabajo. El Artifact conserva evidencia `video`
con perfil, versiones, geometría, timing, fechas, ahorro e intermedios propios.
InstallationAdapter reconoce ese contrato, propone `substitute` y no instala un
resultado `not_beneficial`. Su finalización limpia únicamente rutas propias con
hash acreditado tras completar la operación. No se requiere el candidato borrado
para reanudar una publicación completa.

Las pruebas de integración del orquestador son
`tests/test_pipeline.py`, `tests/test_pipeline_recovery.py` y
`tests/test_pipeline_state.py`; usan servicios simulados y medios sintéticos.
Las integraciones reales del núcleo y de metadata mantienen la marca `integration`.
`test_metadata_integration.py` y `test_metadata_pipeline_integration.py` usan
ExifTool/FFmpeg reales con medios sintéticos; no dependen de los servicios simulados.
Las pruebas `test_video_integration.py` y `test_video_recovery_integration.py`
añaden HandBrake y AAC de FFmpeg reales, modo manual y recuperación entre volúmenes
sintéticos. Declarar revisión visual en esos tests solo prueba el protocolo.

ExportAdapter usa Artifact/StageResult y operaciones export, también al renovar
un derivado propio con huella del destino anterior y backup. La receta conserva
identidad lógica y fuente de mayor calidad de la cadena registrada entre ejecuciones.
No se acredita un destino por existir. `revalidate_completed(pipeline)` se ejecuta
al reanudar antes de comprobar fuentes: invalida export/audit/delivery si cambió
un derivado propio, para repararlo con evidencia sin forzar mutaciones del original.

`prepare_manual(context)` es un hook opcional de preparación de pausa, posterior
a la aprobación. DeliveryAdapter lo usa para copias del alcance auditado. Las
instrucciones de export pueden declarar input_source/output_suffix: la copia manual
usa la fuente archivada verificada, conservando ID y la decisión temporal previa.
`instructions` sigue siendo de solo lectura.

AuditAdapter.finalize registra coverage para exportados/excluidos/pendientes de
todo el alcance. DeliveryAdapter exige esa cobertura y guarda delivery_job en el
mismo journal antes del cliente y antes del backup. Sus decisiones son
delivery_confirmed y delivery_resolution; se consumen por revisión para evitar
reintentos implícitos. Export añade export_quality_reviewed, separado del perfil
de archivo. Véase el [protocolo de cliente](delivery-protocol.md).

Los tests de exportación usan Pillow, ExifTool, HandBrake y FFmpeg reales. El
recorrido final usa esos adaptadores locales reales con transporte remoto simulado;
no demuestra autenticación ni compatibilidad de una cuenta de Google Photos.
