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
| Normalización de vídeo | `UnavailableAdapter`, copias por ID e instrucciones; sin conversor/validador | `validated-video-compression` |
| Compresión | `UnavailableAdapter`, mapa ID/entrada/salida y perfil declarado; sin codificador/validador | `validated-video-compression` |
| Instalación | `InstallationAdapter` real: candidato acreditado → `SafeExecutor.plan/execute`, backup y recuperación; reconoce `applied=True` cuando metadata ya lo publicó | Consume candidatos del servicio integrado |
| Exportación/auditoría | `UnavailableAdapter`, sin acreditar derivados | `verified-export-and-delivery` |
| Entrega manual | Declaración humana diferenciada de prueba API; no ejecuta cargas | `verified-export-and-delivery` |

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
nueva planificación. La revisión final con todos los servicios reales sigue
perteneciendo a `verified-export-and-delivery`.

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
limitado al directorio propio de trabajo. No se implementan presets de vídeo.

Las pruebas de integración del orquestador son
`tests/test_pipeline.py`, `tests/test_pipeline_recovery.py` y
`tests/test_pipeline_state.py`; usan servicios simulados y medios sintéticos.
Las integraciones reales del núcleo y de metadata mantienen la marca `integration`.
`test_metadata_integration.py` y `test_metadata_pipeline_integration.py` usan
ExifTool/FFmpeg reales con medios sintéticos; no dependen de los servicios simulados.
