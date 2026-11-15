---
type: Design
title: Plan de automatización con un comando
description: Diseño propuesto del proceso reanudable, sus fases y las prioridades de implementación.
tags: [propuesto, arquitectura, cli, openspec]
status: draft
sources:
  - id: current
    resource: flujo-actual.md
  - id: settings
    resource: herramientas-externas.md
  - id: openspec
    resource: https://openspec.dev/docs/quickstart
---
# Resultado propuesto

El [núcleo seguro](nucleo-seguro.md) ya está implementado como paquete importable.
El [proceso reanudable](pipeline-reanudable.md) ya implementa el comando y el
control de etapas. [Fechas y nombres](fechas-nombres.md) ya integra ExifTool y
validadores reales, con el ensayo humano de compatibilidad pendiente.
[Vídeo validado](video-validado.md) integra normalización y compresión reales,
pendiente de muestra visual. [Exportación/entrega](exportacion-entrega.md) ya
implementa el recorrido local y un protocolo de cliente; compatibilidad remota
y autenticación específica de gphotos siguen pendientes.

Tras instalar el proyecto y sus herramientas, ejecutar desde cualquier carpeta:

```sh
python3 -m media_library run --config /ruta/media-library.toml
```

**El recorrido local ya está implementado; el transporte remoto se prueba simulado.**
El `pyproject.toml` permite instalarlo en el entorno virtual. Usar `argparse`, `pathlib`,
`tomllib`, `dataclasses`, `zoneinfo` y JSON de la biblioteca estándar es
suficiente para el control; JPEG añade Pillow como extra images. No se necesita
una plataforma de tareas ni una interfaz web.

El modo interactivo mostrará el plan de cambios y pedirá una aprobación del
lote antes de escribir. `--dry-run` generará solo inventario, plan e informes.
`--apply` autorizará el plan automático configurado; nunca sustituirá una
confirmación pendiente de trabajo manual. `--resume <run-id>` recuperará una
ejecución interrumpida y volverá a verificar sus precondiciones.

# Configuración actual

El ejemplo siguiente usa opciones implementadas. `media-library.example.toml`
y las fichas de cada servicio documentan las opciones aceptadas; no existe una
tabla external genérica. La CLI de entrega exige el protocolo documentado.
Un único TOML local, fuera de Git si contiene rutas personales:

```toml
[paths]
source = "/ruta/biblioteca/2026"
workspace = "/ruta/trabajo-media"
archive = "/ruta/originales-conservados"
export = "/ruta/exportacion/2026"

[pipeline.modes]
import_review = "manual"
metadata = "auto"
normalize = "auto"
compression = "auto"
installation = "auto"
export = "auto"
audit = "auto"
delivery = "disabled"

[dates]
timezone = "Europe/Madrid" # Elección explícita del usuario, no deducida de viajes.
policy = "review"         # O filename-to-metadata / metadata-to-filename, explícitas.

[video]
min_bytes = 50000000
profile = "archive-720p30"
frame_rate_mode = "pfr"           # cfr es una opción distinta.
quality_reviewed = false         # Requiere revisión humana antes de instalar.

[export]
images = true
videos = true
image_max_side = 1200
video_profile = "upload-480p30"
video_quality_reviewed = false

[delivery]
mode = "disabled" # Para manual, cambiar también pipeline.modes.delivery.
```

El preflight validará rutas existentes, permisos, espacio estimado para temporales
y backups, versiones y opciones soportadas. Las rutas relativas se resolverán
respecto al TOML. Origen, trabajo, archivo y exportación deben ser disjuntos,
considerando rutas resueltas y enlaces simbólicos. `Europe/Madrid` es un valor
propuesto y configurable por lote/archivo, no una prueba de dónde se capturó
una foto. Las exclusiones serán compartidas por todas las fases.

# Orden y pausas

1. **Preflight e importación**: comprobar dependencias y configuración. Mostrar
   el checklist manual de cargas Dropbox/Drive y descarte; esperar confirmación
   si esa fase está habilitada. No implementar sincronización remota inicial.
2. **Inventario**: recorrer todos los medios independientemente de que el nombre
   sea válido, clasificar formatos reales, fechas y tamaños, y presentar el plan.
3. **Nombres y fechas**: implementado con autoridad por archivo/lote, relectura
   tras escritura selectiva y renombrados recuperables. Normalización MP4 real
   por remux o recodificación combinada, también para vídeos pequeños.
4. **Vídeos grandes**: implementado con selección configurable, HandBrake,
   validación técnica completa y fechas restauradas/releídas. La muestra visual
   necesita revisión humana antes de instalar. Sin ahorro se registra
   `not_beneficial` y se conserva el original, sin reintentos de calidad.
5. **Instalación**: conservar una copia íntegra verificable del original,
   publicar el resultado validado en su álbum y registrar la sustitución.
   Limpiar solo los temporales de operaciones completadas. Retención por defecto
   indefinida: ningún borrado de originales forma parte del proceso inicial.
6. **Exportación**: generar derivados independientes (1200 px y perfil 480p
   actual propuesto), verificar fechas/integridad y registrar cobertura.
7. **Carga y cierre**: mostrar instrucciones y esperar confirmación manual, o
   usar un adaptador CLI configurado expresamente. Guardar comprobante/estado,
   respaldar el estado del uploader tras éxito y emitir informe final.

Las fases siguen el [flujo existente](flujo-actual.md) y sustituyen las tareas
de las [capturas](herramientas-externas.md), con validaciones añadidas.[^current][^settings]

Toda pausa debe indicar archivos exactos, rutas de entrada/salida, ajustes de
la aplicación, objetivo verificable y opciones `comprobar de nuevo`, `posponer`
o `cancelar`. Esperar con entrada de terminal sin consumir CPU. La confirmación
dispara una comprobación; si no se cumple, seguir esperando. Sin terminal,
persistir `WAITING_USER` y salir con código 2; nunca interpretar EOF como «hecho».

# Estado y seguridad operativa

Un manifiesto versionado por ejecución guardará configuración, versiones de
herramientas, ID estable por archivo, ruta relativa, huellas, fecha seleccionada,
decisiones, operaciones, estados y errores. Usar rutas por ID y conservar
jerarquías, sin agrupar por basename. Estados mínimos de ejecución:
`PLANNED`, `RUNNING`, `WAITING_USER`, `FAILED`, `COMPLETED`; estados por operación
de preparación, validación y publicación permiten recuperación por archivo.

Escritura atómica del manifiesto, bloqueo para el mismo origen y registro antes
de cada mutación. Un archivo cambiado desde la planificación requiere nuevo
plan. Recuperar por evidencias verificadas, no por «ya existe». En fallos entre
volúmenes, usar copia verificada y publicación local; no asumir que `move` es
atómico. Ejecutar herramientas con listas de argumentos y comprobar sus salidas.

Códigos implementados: 0 completado, 2 intervención pendiente, 3 fallo operativo,
130 interrupción. Un informe con errores nunca se presenta como éxito total.

# División en cinco cambios

| Orden | Cambio OpenSpec | Entrega verificable | Depende de |
| --- | --- | --- | --- |
| 1 | `safe-execution-core` | Implementado y verificado; pendiente de revisión sin archivar: configuración, inventario, manifiesto y operaciones seguras | — |
| 2 | `resumable-pipeline` | Implementado y verificado sin archivar: comando, plan/aprobación, pausas, reanudación e informes; servicios posteriores simulados solo en tests | 1 |
| 3 | `metadata-and-naming` | Implementado y probado con ExifTool real: fechas EXIF/QuickTime, zona/DST, ambas direcciones, renombrado recuperable y alternativa manual; ensayo humano 3.3 pendiente, sin archivar | 1 y 2 para integración |
| 4 | `validated-video-compression` | Implementado y probado con herramientas reales: normalización MP4, perfil y sustitución recuperable; revisión visual 3.4 pendiente, sin archivar | 1, 3 y 2 para integración |
| 5 | `verified-export-and-delivery` | Derivados, auditoría global, entrega por protocolo y backup implementados/probados con transporte simulado; tarea 2.3 de gphotos real pendiente, sin archivar | 1–4 |

OpenSpec separa propuestas, diseño, requisitos y tareas; su archivo incorpora
los requisitos al estado implementado. Se ha elegido esa separación para que
los agentes posteriores no confundan un diseño con una función existente.[^openspec]
La configuración usa `spec-driven`; los cambios se redactan en español con
marcadores estructurales ingleses. No hay requisitos futuros en `openspec/specs/`
hasta completar su implementación. Inicialización comprobada con OpenSpec 2.0.0.

[^current]: [Flujo manual actual](flujo-actual.md).
[^settings]: [Ajustes externos](herramientas-externas.md).
[^openspec]: [Ciclo oficial de OpenSpec](https://openspec.dev/docs/quickstart).
