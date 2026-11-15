---
type: Reference
title: Proceso reanudable implementado
description: Comando run, alcance, aprobación, pausas, recuperación e informes reales.
tags: [actual, cli, pipeline, recuperacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: command
    resource: ../../src/media_library/__main__.py
  - id: pipeline
    resource: ../../src/media_library/pipeline.py
  - id: adapters
    resource: ../pipeline-adapters.md
  - id: tests
    resource: ../../tests/test_pipeline_recovery.py
---
# Qué funciona

`python -m media_library run --config <toml>` ya existe y funciona desde cualquier
carpeta tras instalar el paquete. Reutiliza configuración, manifiesto versión 1,
journal, bloqueo y operaciones del [núcleo](nucleo-seguro.md). El estado del
orquestador se guarda en checkpoints del mismo journal: no hay un segundo almacén
de control. `resumable-pipeline` está implementado, pendiente de revisión sin
archivar.[^command][^pipeline]

El orden es preflight, revisión de importación, inventario, plan, nombres/fechas,
normalización, compresión, instalación, exportación, auditoría, entrega y cierre.
El TOML elige alcance por patrones de ruta relativa y modos por etapa; las
deshabilitadas figuran como tales. Cada archivo necesita completar sus etapas
anteriores habilitadas para avanzar. Un archivo pendiente no bloquea otros
independientes, pero tampoco puede llegar a instalación o entrega.

El plan muestra IDs, rutas, etapas, herramienta, ajustes, candidatos/destinos y
backups previstos antes de pedir una aprobación del lote. `--apply` sustituye
solo esa aprobación de operaciones automáticas. No elige autoridad de fechas ni
confirma tareas humanas. Las decisiones explícitas se conservan para los servicios
futuros; todavía no se interpretan fechas ni zonas en este cambio.[^pipeline]

# Tres recorridos disponibles

Instalar con `python -m pip install -e '.[dev]'` en un venv y copiar el TOML de
ejemplo a la configuración local. No usar las tablas de fechas/perfiles del plan
futuro como si ya fueran configuración aceptada; el ejemplo actual es la fuente
de opciones disponibles.

1. **Automático con alcance real limitado**: deshabilitar revisión humana,
   metadata, normalize, compression, export, audit y delivery; mantener
   installation en auto. Ejecutar con `--apply`. Inventaría, planifica e informa
   éxito local, conservando originales si no hay candidatos que instalar. El
   informe declara expresamente que no hubo carga. No es una transformación
   integral de la biblioteca.
2. **Corrección manual con servicio simulado**: la prueba
   `python -m pytest tests/test_pipeline.py -k manual_resume` prepara copias por
   ID de dos homónimos, pospone un archivo, corrige otro y reanuda hasta instalar
   ambos mediante el núcleo. El validador es sintético; no acredita EXIF real.
   El comando de producción prepara las mismas pausas, pero el validador EXIF
   aún no está integrado y conserva el pendiente aunque se confirme.
3. **Reanudar sin terminal**: usar
   `python -m media_library run --config /ruta/media-library.toml --resume <run-id>`.
   Revalida las pausas técnicas mediante su adaptador; si falta intervención o
   aprobación, guarda `WAITING_USER` y sale con 2. EOF no confirma nada.

`--dry-run` genera inventario, plan, estado e informe, sin esperar, preparar
copias, transformar medios ni ejecutar entregas. Devuelve 2 porque el plan sigue
sin aplicar. No se puede convertir esa ejecución en aplicación con `--resume
--apply`: crear una ejecución nueva para aplicar. Tampoco admite `--dry-run` y
`--apply` simultáneamente.

# Pausas y recuperación

La pausa incluye ID, etapa, archivos, herramienta, ajustes, entradas/salidas,
condición y evidencia requeridas. Las tareas que modifican medios externamente
trabajan en `workspace/run_id/file_id/manual/etapa/`; nunca se envían originales
a Attributes, Rename o HandBrake desde el programa. La asociación tras un
renombrado exige huella única o una decisión explícita, sin adivinar por nombre
o posición. Dos archivos con bytes idénticos requieren selección explícita si
comparten un conjunto de candidatos.[^adapters]

En terminal se espera con lectura bloqueante. Opciones:

- `comprobar`: llama al validador. Si persiste la discrepancia, conserva la pausa.
- `posponer`: mantiene pendientes y permite continuar archivos independientes.
- `cancelar`: mantiene ese archivo bloqueado; un nuevo plan permite reconsiderarlo.
- `decidir authority=metadata timezone=Europe/Madrid output="/ruta/a/copia"`:
  conserva una decisión explícita. El consumidor debe validarla; por sí sola no
  completa la etapa ni prueba metadatos correctos.

Una confirmación web se registra como **declaración humana**, con
`technical_verification=false`. El programa no carga archivos ni comprueba APIs.
`--apply` no sustituye esa declaración. `--resume` exige configuración y adaptadores
iguales a los congelados; cambios externos del original exigen un nuevo plan
para ese archivo, preservando las evidencias del resto.

Los resultados validados se registran antes de publicar y la etapa solo termina
después de acreditar sus operaciones. Reanudar confirma publicaciones verificadas
sin repetir productores. Si se interrumpió antes de guardar la validación, el
adaptador debe revalidar las operaciones recuperadas; no se presumen completas.
Ctrl+C, SIGHUP y SIGTERM preservan el punto de interrupción y devuelven 130. Tras
una caída dura, revisar el bloqueo y usar `--recover-stale-lock` junto con resume;
jamás desplaza un escritor activo.[^pipeline]

# Informes, adaptadores y límites

`plan.json` e `report.json` viven junto al manifiesto/journal. La consola resume
resultados por etapa, cambios, conservados, omitidos, pendientes, fallos y siguiente
orden de reanudación. Códigos: 0 alcance completado, 2 pendientes, 3 fallo operativo,
130 interrupción. Si el disco impide guardar informes, se conserva el último
estado duradero y se muestra el fallo y la ruta de recuperación.

Son reales el control de etapas, las pausas, planificación, estado, inventario,
instalación segura e informes. Son declaraciones humanas la revisión de importación
y la entrega web. Nombres/EXIF, normalización, compresión, exportación y auditoría
de medios usan adaptadores pendientes: no hay validación técnica por defecto y
no pueden declararse completados. Los adaptadores que simulan esos servicios
solo se inyectan en tests; el informe los identifica como simulados.[^adapters]

La suite demuestra el recorrido completo con servicios simulados y operaciones
reales sobre temporales. No demuestra compatibilidad EXIF, perfiles de vídeo,
calidad visual ni una entrega remota integral. Esas integraciones siguen en las
otras tres propuestas. Se conservan los límites de bloqueo y filesystem del núcleo.
No se ha utilizado biblioteca personal ni realizado carga remota.[^tests]

[^command]: [Entrada de consola](../../src/media_library/__main__.py).
[^pipeline]: [Orquestador persistente](../../src/media_library/pipeline.py).
[^adapters]: [Contrato y puntos de integración](../pipeline-adapters.md).
[^tests]: [Pruebas de recuperación y recorrido](../../tests/test_pipeline_recovery.py).
