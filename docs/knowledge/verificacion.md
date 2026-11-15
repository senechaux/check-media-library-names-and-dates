---
type: Reference
title: Verificación del núcleo y servicios de medios
description: Pruebas del pipeline, fechas y vídeo real con medios sintéticos y revisiones humanas pendientes.
tags: [verificacion, tests, seguridad, documentacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: tests
    resource: ../../tests/
    title: Tests ejecutables del núcleo
  - id: core
    resource: nucleo-seguro.md
    title: Comportamiento implementado y límites
  - id: history
    resource: auditoria-actual.md
    title: Evidencia histórica de nombres y fechas
  - id: scope
    resource: alcance.md
  - id: pipeline
    resource: pipeline-reanudable.md
  - id: dates
    resource: fechas-nombres.md
  - id: video
    resource: video-validado.md
---
# Comprobaciones del 2026-11-15

| Comprobación | Resultado y alcance |
| --- | --- |
| Instalación | Venv temporal con Python 3.12.15 y pytest 9.2.0; importación desde otra carpeta y `pip check` correctos. Wheel construido con dependencias de build aisladas; preset JSON importable desde el wheel fuera del repositorio. |
| Suite rápida | 173 pruebas pasadas con `python -m pytest`: 139 existentes y 34 nuevas de planificación de vídeo, publicación recuperable y grupos ExifTool; las 45 integraciones se excluyen por marca. |
| Herramientas reales | 45 integraciones pasadas con `python -m pytest -m integration`: 20 previas y 25 de vídeo, con ExifTool 13.40, FFmpeg/ffprobe 9.0.2 y HandBrake 1.11.2; ninguna omitida en esta máquina. |
| Configuración | Rutas relativas al TOML, solapamientos por symlinks/mayúsculas, permisos, capacidades y estimación de espacio agregado por volumen. Preflight sin crear destinos. |
| Inventario y procesos | Profundidades variadas, formatos independientes del nombre, mismo basename/bytes con IDs distintos, Unicode, nombres especiales literales, ilegibles, FIFOs, symlinks, timeout, no cero y parcial sin publicar. |
| Backups y recuperación | Hash, conflictos de destino/backup/temporal, cambios externos antes y después del backup, falta de espacio y fallo de copia parcial sin tocar el original. |
| Persistencia e interrupción | Fallos de guardado antes/después de publicación, snapshots anterior/nuevo completos, replay del journal, cola incompleta, corrupción rechazada, bloqueo concurrente y obsoleto, salida abrupta real, restauración interrumpida. |
| Integridad del estado | Versiones desconocidas y configuración distinta se rechazan; no se sigue un journal enlazado; las operaciones acreditadas no repiten el productor. |
| Orquestador | CLI instalada desde otra carpeta, alcance y dependencias por archivo, simulación sin copias/mutadores ni espera, aprobación única, EOF/no TTY, decisiones persistentes, confirmación con revalidación y declaración web diferenciada. |
| Recuperación del pipeline | Interrupciones al planificar y antes/después de publicar, fallo de guardado tras publicación, Ctrl+C y SIGHUP reales durante espera TTY, sin repetir productores acreditados. |
| Recorrido manual y servicios | Dos homónimos con copias, IDs y backups separados; un pendiente no bloquea el otro; renombrados asociados por huella/decisión. Recorrido completo con servicios simulados e instalación segura real. |
| Fechas | Coincidencias, discrepancia de 2 h 59 min, ISO/EXIF, offsets y fracciones, precisión parcial sin completar, fechas inválidas/ausentes y errores por archivo aislados. Calendario parcial comparado en la zona declarada. |
| Zona y DST | Sin inferir la zona del host; fold 0/1 del invierno releído en UTC con ExifTool real, verano, hora inexistente que exige otra fecha y offsets contradictorios diagnosticados. |
| Escritura selectiva | JPEG y MP4/MOV sintéticos con ExifTool real: campos objetivo releídos, fracciones conservadas, metadatos ajenos extraídos y contenido codificado iguales, legibilidad decodificada. FileModifyDate y FileCreateDate comprobados por separado en macOS con SetFile, también después de renombrar. |
| Nombres y recuperación | Reservas, sufijos, ciclos y mayúsculas/Unicode, prefijos históricos y cambios externos. Integración de ciclo de dos nombres y cinco puntos de interrupción; reanudación sin repetir escrituras, backups íntegros y segunda ejecución sin mutaciones. |
| Vídeo | Horizontal 1920×1080 →1280×720, vertical 1080×1920 →720×1280, matriz rotada, SAR 4:3, 24/60 FPS PFR y CFR 30; pistas silenciosas/audio real, MP4 y MOV, remux de paquetes íntegros y fechas releídas. |
| Seguridad de vídeo | Manual correcto/corrupto revalidado, revisión visual como declaración separada, HDR/múltiples pistas pendientes, resultado realmente mayor y ahorro mínimo no alcanzado, dos álbumes con una colisión y temporales independientes. |
| Otro volumen | Imagen HFS+ sintética de 64 MB montada en temporal, con st_dev distinto del origen. Workspace y archivo en ella; ocho interrupciones hasta limpieza, con original/salida/backup íntegros y una sola codificación al reanudar. |
| OpenSpec 2.0.0 | Núcleo, pipeline, metadata y vídeo válidos en modo estricto. Metadata: ensayo humano 3.3 pendiente; vídeo: muestra visual 3.4 pendiente. Ambos 10/11 tareas verificadas; ningún cambio archivado. |
| Documentación | Frontmatter OKF parseable, índices/log reservados, versión 0.2 y destinos de enlaces Markdown locales existentes. |
| Git | Commits descriptivos en `changes-by-codex`, con push tras cada commit; upstream configurado, sin force push. |

Las integraciones generan un vídeo mínimo con FFmpeg, verifican contenedor/codec
con ffprobe y ejercitan los tags del adaptador histórico. La segunda prepara un
candidato real con HandBrake, valida stream/duración y lo publica mediante el
núcleo, comprobando que el origen permanece intacto. Estos dos casos del núcleo
no acreditan por sí solos el perfil nuevo ni exigen tamaño exacto de salida.[^tests]

Los 37 casos del orquestador prueban el control del proceso. Los adaptadores simulados solo se inyectan
en tests; el comando de producción conserva los pendientes si falta un validador.
Las pruebas de señales usan un proceso real con pseudo-terminal y comprueban
código 130, estado guardado y bloqueo liberado. Las correcciones manuales son
de contenido sintético y los renombrados se asocian sin adivinar por basename.[^pipeline]

Las 18 integraciones nuevas de metadata ejercitan herramientas reales: 5 casos
del escritor/atributos y 13 del pipeline. Comprueban ambas direcciones, copias
corregidas manualmente y revalidadas, decisiones persistentes, prefijos,
idempotencia y recuperación. Los 8 tests rápidos de contrato ExifTool usan datos/fallos simulados;
no se cuentan como prueba de compatibilidad real.[^dates]

Los 25 casos nuevos de vídeo son 9 de perfil/pipeline y 16 de pausas/fallos y
recuperación. Se han usado los codificadores y lectores reales. La corrupción
manual conserva contenedor/cabeceras y rompe un paquete de vídeo: ffprobe puede
inspeccionarlo y la decodificación impide publicar, aunque el candidato sea menor.
La revisión visual declarada por los tests prueba solo el protocolo, no calidad.
El AAC predeterminado de FFmpeg pasó; el ca_aac de Apple falló al inicializar en
este entorno y no se presenta como integración compatible.[^video]

Las interrupciones parametrizadas cubren intención, backup, intención de
publicación, publicación y confirmación para replace/rename/export cuando
corresponde. Una prueba termina un proceso mediante `os._exit` justo después
de reemplazar el medio, sin limpiar el bloqueo ni confirmar el resultado. La
recuperación requiere reconocer el bloqueo obsoleto y acredita la publicación
por hash/backup sin volver a transformar el archivo.[^tests]

# Comandos reproducibles

Desde la raíz, con Python >=3.11 y las herramientas opcionales en PATH:

```sh
python3 -m venv .venv-core
. .venv-core/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m pytest -m integration
python -m pip check
npx --yes --package @fission-ai/openspec@2.0.0 openspec validate safe-execution-core --strict --no-interactive
npx --yes --package @fission-ai/openspec@2.0.0 openspec validate resumable-pipeline --strict --no-interactive
npx --yes --package @fission-ai/openspec@2.0.0 openspec validate metadata-and-naming --strict --no-interactive
npx --yes --package @fission-ai/openspec@2.0.0 openspec validate validated-video-compression --strict --no-interactive
git diff --check
```

Las integraciones se omiten con motivo si falta ExifTool, FFmpeg, ffprobe o HandBrakeCLI;
una omisión no acredita compatibilidad. La sesión utilizó OpenSpec 2.0.0 desde
la caché npm local y un entorno Python en `/private/tmp`, sin instalar herramientas
globales. ExifTool 13.40 se extrajo del repositorio oficial en `/private/tmp`;
los tests lo seleccionaron con `MEDIA_LIBRARY_EXIFTOOL=/ruta/exiftool`.
Esa variable es exclusiva de tests: el producto usa PATH o `[tools.exiftool]`.
Las ocho pruebas entre volúmenes requieren `MEDIA_LIBRARY_TEST_VOLUME` apuntando
a un volumen temporal aislado con dispositivo distinto; sin él se omiten con
motivo y no acreditan esa recuperación. En esta sesión se creó/montó una imagen
HFS+ sintética bajo `/private/tmp` y se indicó su punto de montaje al ejecutar
las 45 integraciones. No usar una ruta que contenga medios personales.
La estructura OKF y los enlaces se revisaron mediante una comprobación
puntual con el parser YAML local; no se añadió un validador al producto.

# Evidencia histórica y trabajo pendiente

Las tres anomalías reproducidas el 2026-11-13 (igualdad de vídeo rechazada,
diferencia de 2 h 59 min aceptada como zona y patrón 16 sin aplicar) corresponden
a los scripts históricos. El servicio nuevo usa comparación por precisión/zona
y mantiene las fechas parciales pendientes de una decisión; esas regresiones
están cubiertas. No se ha cambiado la lógica temporal de los scripts antiguos.
Las fichas históricas señalan los adaptadores que sí cambiaron:
contador sin shell, procesos comprobados y movimientos compartidos sin errores
ocultos.[^history]

No se ha usado la biblioteca personal, la Papelera, credenciales ni cargas
remotas. Los originales de las pruebas son sintéticos y viven en temporales.
No se han probado fallos físicos de alimentación, discos físicos distintos,
ACL/resource forks, ni bloqueo entre máquinas. La recuperación se acredita en
el sistema local; las operaciones comparan huellas frente a cambios externos,
pero otros editores no participan en el bloqueo del programa.[^core]

ExifTool está acreditado en los formatos indicados; no se acredita escritura
universal PNG/GIF/HEIC. La tarea 3.3 sigue pendiente: Attributes/Rename, fechas
vistas en Apple Photos y equivalencia con su modo Brute Force requieren un ensayo
humano. La ficha de fechas detalla las copias, datos y evidencia a registrar.
La orientación y el perfil de vídeo tienen validación técnica real. La muestra
visual RF 22 sigue pendiente en vídeo 3.4; su ficha describe cómo revisar detalle,
movimiento y sincronía antes de aprobar un lote. HDR/pistas avanzadas conservan
pausa sin política. Exportación/entrega sigue sin implementar. No se presentan
servicios simulados ni declaraciones humanas como validaciones reales superadas.
Los documentos siguen en `draft`, sin atribuir una aprobación humana.[^scope]

[^tests]: [Suite del núcleo](../../tests/).
[^core]: [Núcleo seguro implementado](nucleo-seguro.md).
[^history]: [Regresiones históricas](auditoria-actual.md).
[^scope]: [Alcance y procedencia](alcance.md).
[^pipeline]: [Proceso reanudable implementado](pipeline-reanudable.md).
[^dates]: [Servicio de fechas, evidencia real y ensayo humano pendiente](fechas-nombres.md).
[^video]: [Vídeo real, evidencia y revisión visual pendiente](video-validado.md).
