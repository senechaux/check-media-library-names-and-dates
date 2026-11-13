---
type: Policy
title: Política de tests del desarrollo
description: Pruebas automatizadas proporcionadas al riesgo y mantenibles para los cambios previstos.
tags: [propuesto, tests, calidad]
status: draft
sources:
  - id: user
    resource: "Petición del usuario del 2026-11-14 de incluir una cantidad razonable de tests"
  - id: plan
    resource: automatizacion.md
---
# Objetivo

El desarrollo debe incluir una cantidad razonable de tests automatizados.
La suficiencia se juzga por los comportamientos y riesgos cubiertos, sin fijar
una cantidad de tests ni un porcentaje de cobertura obligatorio.[^user]

# Qué probar

| Área | Casos prioritarios |
| --- | --- |
| Fechas y nombres | Igualdad, discrepancias, offsets, DST, fechas inválidas/parciales, colisiones e idempotencia. |
| Operaciones de archivos | Homónimos en álbumes distintos, destinos existentes, backup, cambios externos e interrupciones durante publicación. |
| Orquestador | Simulación sin modificar medios, pausas, EOF, códigos de salida y reanudación sin repetir operaciones completas. |
| Vídeos y exportación | Orientación/rotación, límites de tamaño/FPS, fechas conservadas, procesos fallidos y salidas parciales o inválidas. |
| Entrega | Carga incierta, error del cliente y fallo de backup tras una entrega ya acreditada, usando un cliente simulado. |

Estos casos desarrollan los escenarios de las cinco propuestas existentes;
no requieren una prueba diferente por cada fila o escenario si una prueba
parametrizada comprueba varios comportamientos relacionados.[^plan]

# Organización propuesta

- Usar pytest como dependencia de desarrollo y ofrecer una suite rápida con
  `python -m pytest`. Instalar y documentar esta dependencia al implementar el núcleo.
- Priorizar tests unitarios de lógica con resultados observables y tests sobre
  directorios temporales para operaciones de archivos.
- Simular procesos externos en la suite rápida para inyectar fallos concretos.
  Añadir un conjunto pequeño de integraciones con ExifTool/FFmpeg/HandBrakeCLI
  reales y medios sintéticos pequeños: los mocks no demuestran compatibilidad.
- Separar integraciones mediante una marca documentada. Si falta una herramienta,
  informar del test omitido y su motivo; no presentarlo como integración superada.
- Añadir una regresión automatizada al corregir un fallo relevante. Ejecutar
  los tests afectados y la suite rápida antes de dar por terminado el cambio.
- Comprobar Apple Photos y calidad visual manualmente cuando corresponda,
  dejando evidencia y límites; esas revisiones complementan la automatización.

# Límites de esfuerzo

Evitar tests de getters, constantes, mensajes exactos sin contrato, detalles
internos o mocks que únicamente confirmen llamadas. No añadir tests por cambios
de documentación o formato. No buscar cobertura total por obligación.

Todas las pruebas deben poder trabajar sin biblioteca personal, credenciales
ni cargas reales. No guardar medios personales en Git. Las pruebas de integración
deben validar contenido y resultados, sin depender de tiempos exactos de ejecución
o del tamaño exacto producido por una versión concreta del codificador.

Esta política es planificación: todavía no se ha añadido una suite ni se ha
implementado el nuevo programa.

[^user]: Preferencia explícita del usuario recibida el 2026-11-14.
[^plan]: [Plan de automatización](automatizacion.md).
