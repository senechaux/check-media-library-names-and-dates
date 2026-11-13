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

Tras instalar el proyecto y sus herramientas, ejecutar desde cualquier carpeta:

```sh
python3 -m media_library run --config /ruta/media-library.toml
```

**Es una interfaz propuesta, aún no existe.** Un `pyproject.toml` permitirá
instalar el paquete en el entorno virtual. Usar `argparse`, `pathlib`,
`tomllib`, `dataclasses`, `zoneinfo` y JSON de la biblioteca estándar es
suficiente; no se necesita una plataforma de tareas ni una interfaz web.

El modo interactivo mostrará el plan de cambios y pedirá una aprobación del
lote antes de escribir. `--dry-run` generará solo inventario, plan e informes.
`--apply` autorizará el plan automático configurado; nunca sustituirá una
confirmación pendiente de trabajo manual. `--resume <run-id>` recuperará una
ejecución interrumpida y volverá a verificar sus precondiciones.

# Configuración propuesta

Un único TOML local, fuera de Git si contiene rutas personales:

```toml
[paths]
source = "/ruta/biblioteca/2026"
workspace = "/ruta/trabajo-media"
archive = "/ruta/originales-conservados"
export = "/ruta/exportacion/2026"

[dates]
default_timezone = "Europe/Madrid" # Propuesta para fechas sin offset; no deducida de viajes.
conflict_policy = "review"        # O filename-to-metadata / metadata-to-filename, explícitas.

[compression]
min_bytes = 50000000
profile = "archive-720p30"
frame_rate_mode = "pfr"           # cfr es una opción distinta.
portrait_bounds = "720x1280"     # Alternativa revisable: height-720.

[export]
enabled = true
image_max_side = 1200
video_profile = "upload-480p30"

[external]
metadata = "auto"                # auto | manual
rename = "auto"                  # auto | manual
compression = "auto"             # auto | manual
upload = "manual"                # disabled | manual | configured-cli
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
3. **Nombres y fechas**: proponer normalización y resolver conflictos eligiendo
   autoridad por archivo/lote. Convertir formatos no MP4 solo cuando el plan
   lo incluya. Volver a auditar tras cada acción manual o automática.
4. **Vídeos grandes**: seleccionar, comprimir a temporal y validar; restaurar
   las fechas seleccionadas y ofrecer revisión visual de la muestra. Si el
   tamaño no disminuye, registrar y dejar el original, sin reintentos infinitos.
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

Códigos propuestos: 0 completado, 2 intervención pendiente, 3 fallo operativo,
130 interrupción. Un informe con errores nunca se presenta como éxito total.

# División en cinco cambios

| Orden | Cambio OpenSpec | Entrega verificable | Depende de |
| --- | --- | --- | --- |
| 1 | `safe-execution-core` | Configuración, inventario fiable, manifiesto, operaciones seguras y corrección de resultados básicos | — |
| 2 | `resumable-pipeline` | Comando único, plan/aplicación, pausas y reanudación usando contratos de etapa | 1 |
| 3 | `metadata-and-naming` | Fechas EXIF/QuickTime, zona, renombrado en ambas direcciones y alternativa manual | 1 y 2 para integración |
| 4 | `validated-video-compression` | Perfil 720p30, orientación, conversión MP4 y sustitución validada | 1, 3 y 2 para integración |
| 5 | `verified-export-and-delivery` | Derivados, auditoría final, carga opcional y backup del estado | 1–4 |

OpenSpec separa propuestas, diseño, requisitos y tareas; su archivo incorpora
los requisitos al estado implementado. Se ha elegido esa separación para que
los agentes posteriores no confundan un diseño con una función existente.[^openspec]
La configuración usa `spec-driven`; los cambios se redactan en español con
marcadores estructurales ingleses. No hay requisitos futuros en `openspec/specs/`
hasta completar su implementación. Inicialización comprobada con OpenSpec 2.0.0.

[^current]: [Flujo manual actual](flujo-actual.md).
[^settings]: [Ajustes externos](herramientas-externas.md).
[^openspec]: [Ciclo oficial de OpenSpec](https://openspec.dev/docs/quickstart).
