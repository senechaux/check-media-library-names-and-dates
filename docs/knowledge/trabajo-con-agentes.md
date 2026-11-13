---
type: Playbook
title: Revisión e implementación con agentes
description: Orden de revisión, reparto de tareas, decisiones abiertas y skills útiles para implementar el plan.
tags: [propuesto, agentes, openspec, skills]
status: draft
sources:
  - id: plan
    resource: automatizacion.md
  - id: propose
    resource: https://skills.sh/fission-ai/openspec/openspec-propose
  - id: archive
    resource: https://skills.sh/fission-ai/openspec/openspec-archive-change
  - id: upstream
    resource: https://github.com/Fission-AI/OpenSpec
  - id: okf-skill
    resource: https://github.com/inkeep/open-knowledge-skills/blob/main/skills/starter-packs/okf-knowledge-base/okf-knowledge-base/SKILL.md
---
# Cómo revisar lo entregado

1. Leer [flujo actual](flujo-actual.md) y las tres fichas de scripts.
2. Revisar [transcripción de ajustes](herramientas-externas.md) y
   [plan general](automatizacion.md).
3. En cada cambio de `openspec/changes/`, revisar `proposal.md`, después
   `specs/*/spec.md` (qué se aceptará), `design.md` y `tasks.md`.
4. Implementar el cambio correspondiente y marcar una tarea únicamente al
   completar su verificación. Archivar tras comprobar código, escenarios y
   documentación; solo entonces sus requisitos pasan a `openspec/specs/`.

Todas las tareas de implementación están pendientes. La documentación OKF es
una instantánea del código; las propuestas OpenSpec describen el futuro.

# Reparto posterior

| Cambio | Responsabilidad sugerida | Momento |
| --- | --- | --- |
| `safe-execution-core` | Configuración, modelos, inventario, manifiesto, bloqueo y operaciones base | Primero; fijar contratos antes de repartir módulos. |
| `resumable-pipeline` | CLI, etapas, pausas y recuperación | Tras el núcleo; puede avanzar con adaptadores simulados. |
| `metadata-and-naming` | Parser, decisiones, ExifTool y nombres | Tras el núcleo; lógica independiente en paralelo al pipeline, integración después. |
| `validated-video-compression` | Perfil, geometría, codificación, validación e instalación | Tras acordar las interfaces de fecha y operación; integrar con pipeline. |
| `verified-export-and-delivery` | Derivados, auditoría final, entrega y prueba integral | Tras estabilizar los cuatro anteriores. |

Para varios agentes, usar ramas/worktrees separados y asignar un responsable
por módulo. Congelar primero `StageResult`, `CaptureDate`, operaciones y esquema
del manifiesto. El servicio de vídeo debe tener un único responsable: exportación
lo consume. Rebasar/integrar cambios pequeños, sin dos agentes editando a la vez
`common_functions.py` o el mismo manifiesto de una ejecución real.[^plan]

Prompt inicial sugerido para la siguiente sesión:

> Lee `docs/knowledge/index.md` y los artefactos de
> `openspec/changes/safe-execution-core/`. Implementa solo ese cambio, siguiendo
> sus escenarios y tareas. Prueba en temporales o fixtures sintéticos; no ejecutes
> sobre mi biblioteca. Conserva las entradas antiguas, actualiza la documentación
> de lo implementado y crea commits pequeños. No hagas push.

El paralelismo aporta más valor después de fijar interfaces que al repartir
scripts heredados completos. Un revisor puede comprobar escenarios y fallos
inyectados en otro worktree sin ejecutar el proceso sobre originales personales.

# Prioridades y decisiones para revisar

| Prioridad | Punto | Propuesta inicial / comprobación pendiente |
| --- | --- | --- |
| P0 | Coincidencias de vídeo marcadas como error y heurística de 1–2 horas | Comparación temporal correcta, con pruebas de regresión en metadata-and-naming. |
| P0 | Sobrescrituras, homónimos y limpieza de pendientes | Núcleo seguro y publicación por operación antes de automatizar sustituciones. |
| P0 | Procesos fallidos o archivos parciales tratados como éxito | Códigos comprobados y validación de contenido antes de publicar. |
| P1 | ¿Qué fecha manda? | `review` por defecto; elegir por lote/archivo. No hace falta imponer una única dirección. |
| P1 | «720p» en vertical | Recomendada 720×1280; `height-720` si se prefiere el tamaño visual aproximado de la captura. |
| P1 | «30 frames» | PFR <=30, como la captura; CFR 30 si se desea tasa constante. |
| P1 | Calidad y ahorro | RF 22 es una propuesta inicial, no un ajuste inferido de la captura; revisar una muestra. |
| P1 | Zona de fechas sin offset | Europe/Madrid configurable; revisar lotes de viajes y DST antes de escribir. |
| P1 | Compatibilidad Apple Photos | Ensayo local comparando Attributes y ExifTool; conservar paso manual hasta demostrarla. |
| P2 | Carga de Google Photos | Manual inicialmente; activar CLI solo tras comprobar versión, alcance y evidencia. |
| P2 | Doble compresión para exportar | Usar el original conservado y la misma decisión de fecha para crear el derivado de carga. |

Recomendaciones adicionales: empezar con un álbum pequeño y representativo;
separar revisión visual de comprobación técnica; conservar originales sin borrado
automático; usar informes con rutas completas y motivos de omisión; considerar
una detección de duplicados por hash como mejora posterior, sin eliminación
automática. Sincronización remota, deduplicación y gestión de álbumes no deben
retrasar el primer comando local fiable.

# Skills evaluadas

Se utilizó la skill local `find-skills` para consultar el directorio y ejecutar
`npx skills find openspec`. No se instaló ninguna skill ni integración de agente.
Las cifras siguientes son observaciones del 2026-11-13, no criterios de corrección.

- **openspec-propose**, del proyecto oficial Fission-AI: aproximadamente 4,5 mil
  instalaciones en la consulta; el repositorio oficial mostraba unas 74,8 mil
  estrellas. Útil para nuevas propuestas y mantener alcance/requisitos/tareas.
  Se revisaron su página y sus instrucciones, además de la documentación oficial.[^propose][^upstream]
- **openspec-archive-change**, del mismo proyecto: aproximadamente 4,4 mil
  instalaciones. Útil al terminar cambios para consolidar las especificaciones;
  su uso no equivale a publicar ni hacer push.[^archive]
- **Skill propia de mantenimiento de medios**, aún no creada: reuniría en una
  página dónde están OKF/OpenSpec, cómo probar con fixtures, cómo comprobar fechas,
  rotación y recuperación y qué evidencia aportar. La skill disponible
  `skill-creator` serviría para crearla cuando existan comandos estables.
- **okf-knowledge-base**, de Inkeep: candidata para mantener procedencia y
  estructura OKF. Sus instrucciones se han inspeccionado; no se comprobó adopción
  suficiente para recomendar su instalación inicial y declara integración con
  OpenKnowledge. El paquete Markdown actual no requiere esa aplicación.[^okf-skill]

Instalaciones opcionales para una sesión posterior, revisando antes su contenido:

```sh
npx skills add fission-ai/openspec@openspec-propose
npx skills add fission-ai/openspec@openspec-archive-change
```

Para obtener la integración oficial completa de OpenSpec con el agente, usar
el `init --tools codex --language Spanish` de la versión elegida y revisar sus
archivos generados. En esta tarea se ejecutó `init --tools none`, sin crear
instrucciones ni skills específicas del editor. No conviene añadir paquetes
genéricos de vídeo sin comprobar que cubren EXIF/QuickTime y los fallos de este
proyecto; las herramientas CLI y las pruebas concretas son el fundamento.

[^plan]: [Arquitectura y dependencias propuestas](automatizacion.md).
[^propose]: [Skill oficial openspec-propose](https://skills.sh/fission-ai/openspec/openspec-propose).
[^archive]: [Skill oficial openspec-archive-change](https://skills.sh/fission-ai/openspec/openspec-archive-change).
[^upstream]: [Repositorio oficial de OpenSpec](https://github.com/Fission-AI/OpenSpec).
[^okf-skill]: [Instrucciones de okf-knowledge-base](https://github.com/inkeep/open-knowledge-skills/blob/main/skills/starter-packs/okf-knowledge-base/okf-knowledge-base/SKILL.md).
