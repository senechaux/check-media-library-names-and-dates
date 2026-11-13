---
type: Reference
title: Alcance y procedencia
description: Cómo interpretar esta documentación y distinguir observaciones de propuestas.
tags: [proyecto, documentacion, okf]
status: draft
x_snapshot_commit: bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c
x_analysis_date: "2026-11-13"
sources:
  - id: repository
    resource: https://github.com/senechaux/check-media-library-names-and-dates/tree/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c
    title: Código y README analizados
  - id: okf
    resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: Especificación OKF v0.2 consultada el 2026-11-13
---
# Alcance

Este paquete documenta los ocho archivos Python y el lanzador Bash presentes en
el commit indicado. El código tiene prioridad sobre el README cuando difieren.
El objetivo del proyecto es ordenar una biblioteca local de fotos y vídeos,
detectar problemas de nombres y fechas y preparar copias para Google Photos.[^repository]

El análisis combina lectura de todas las funciones y seguimiento de las llamadas
desde cada `main()`. Las comprobaciones sintéticas se identifican expresamente.
No se ha ejecutado el proceso sobre la biblioteca personal, ni se ha comprobado
la sincronización con Dropbox, Google Drive, Apple Photos o Google Photos.

# Convenciones

- **Actual**: comportamiento que se observa en el código de referencia.
- **Hallazgo**: defecto o limitación, con evidencia y efecto concreto.
- **Propuesto**: decisión de diseño pendiente de implementar y revisar.
- **Pendiente de comprobar**: una captura o el código no permiten demostrarlo.

Los conceptos usan Markdown UTF-8 con frontmatter YAML y enlaces ordinarios.
`index.md` identifica la versión del paquete; `log.md` conserva su historial.
Se omite `verified`: una revisión del agente no equivale a una aprobación humana.
Los documentos permanecen en `draft` hasta su revisión.[^okf]

Las fuentes del código apuntan al commit completo para conservar su procedencia
aunque los scripts cambien. Los enlaces relativos entre conceptos permiten
copiar `docs/knowledge/` como paquete independiente. Las fuentes web con `main`
o `latest` reflejan la consulta indicada y pueden cambiar posteriormente.

Las tres capturas del usuario se transcriben en la documentación de planificación.
No se guardan imágenes de la biblioteca ni se inventa una ruta a los adjuntos.

# Mantenimiento

Al implementar una capacidad, actualizar la documentación del comportamiento
actual y su referencia al código. Los requisitos propuestos vivirán en
`openspec/changes/`; solo pasarán a `openspec/specs/` cuando estén implementados
y verificados. Evitar copiar las mismas reglas completas en ambos lugares.

[^repository]: [Repositorio en el commit analizado](https://github.com/senechaux/check-media-library-names-and-dates/tree/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c).
[^okf]: [Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md).
