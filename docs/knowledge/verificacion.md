---
type: Reference
title: Verificación del núcleo y del plan
description: Evidencia de pruebas del núcleo y orquestador, integraciones y límites pendientes.
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
---
# Comprobaciones del 2026-11-15

| Comprobación | Resultado y alcance |
| --- | --- |
| Instalación | `pip install -e '.[dev]'` en venv temporal con Python 3.12.15 y pytest 9.2.0; importación desde otra carpeta y `pip check` correctos. |
| Suite rápida | 97 pruebas pasadas con `python -m pytest`: 60 existentes del núcleo y 37 nuevas del pipeline; las 2 integraciones se excluyen por marca. |
| Herramientas reales | 2 integraciones pasadas con `python -m pytest -m integration`: FFmpeg/ffprobe 9.0.2 y HandBrake 1.11.2, sin omisiones en esta máquina. |
| Configuración | Rutas relativas al TOML, solapamientos por symlinks/mayúsculas, permisos, capacidades y estimación de espacio agregado por volumen. Preflight sin crear destinos. |
| Inventario y procesos | Profundidades variadas, formatos independientes del nombre, mismo basename/bytes con IDs distintos, Unicode, nombres especiales literales, ilegibles, FIFOs, symlinks, timeout, no cero y parcial sin publicar. |
| Backups y recuperación | Hash, conflictos de destino/backup/temporal, cambios externos antes y después del backup, falta de espacio y fallo de copia parcial sin tocar el original. |
| Persistencia e interrupción | Fallos de guardado antes/después de publicación, snapshots anterior/nuevo completos, replay del journal, cola incompleta, corrupción rechazada, bloqueo concurrente y obsoleto, salida abrupta real, restauración interrumpida. |
| Integridad del estado | Versiones desconocidas y configuración distinta se rechazan; no se sigue un journal enlazado; las operaciones acreditadas no repiten el productor. |
| Orquestador | CLI instalada desde otra carpeta, alcance y dependencias por archivo, simulación sin copias/mutadores ni espera, aprobación única, EOF/no TTY, decisiones persistentes, confirmación con revalidación y declaración web diferenciada. |
| Recuperación del pipeline | Interrupciones al planificar y antes/después de publicar, fallo de guardado tras publicación, Ctrl+C y SIGHUP reales durante espera TTY, sin repetir productores acreditados. |
| Recorrido manual y servicios | Dos homónimos con copias, IDs y backups separados; un pendiente no bloquea el otro; renombrados asociados por huella/decisión. Recorrido completo con servicios simulados e instalación segura real. |
| OpenSpec 2.0.0 | `safe-execution-core` y `resumable-pipeline` válidos en modo estricto; tareas completadas tras verificar comportamiento. Ambos sin archivar. |
| Documentación | Frontmatter OKF parseable, índices/log reservados, versión 0.2 y destinos de enlaces Markdown locales existentes. |
| Git | Commits descriptivos en `changes-by-codex`, con push tras cada commit; upstream configurado, sin force push. |

Las integraciones generan un vídeo mínimo con FFmpeg, verifican contenedor/codec
con ffprobe y ejercitan los tags del adaptador histórico. La segunda prepara un
candidato real con HandBrake, valida stream/duración y lo publica mediante el
núcleo, comprobando que el origen permanece intacto. No valida el perfil futuro
de compresión ni exige un tamaño exacto de salida.[^tests]

Los 37 casos nuevos prueban el control del proceso, no implementan EXIF ni los
codificadores/exportadores futuros. Los adaptadores simulados solo se inyectan
en tests; el comando de producción conserva los pendientes si falta un validador.
Las pruebas de señales usan un proceso real con pseudo-terminal y comprueban
código 130, estado guardado y bloqueo liberado. Las correcciones manuales son
de contenido sintético y los renombrados se asocian sin adivinar por basename.[^pipeline]

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
git diff --check
```

Las integraciones se omiten con motivo si falta FFmpeg, ffprobe o HandBrakeCLI;
una omisión no acredita compatibilidad. La sesión utilizó OpenSpec 2.0.0 desde
la caché npm local y un entorno Python en `/private/tmp`, sin instalar herramientas
globales. La estructura OKF y los enlaces se revisaron mediante una comprobación
puntual con el parser YAML local; no se añadió un validador al producto.

# Evidencia histórica y trabajo pendiente

Las tres anomalías de nombres/fechas reproducidas el 2026-11-13 siguen
perteneciendo a `metadata-and-naming`: igualdad de vídeo rechazada, diferencia
de 2 h 59 min aceptada como zona y patrón 16 sin aplicar. El núcleo no cambia
esa lógica. Las fichas de los scripts señalan los adaptadores que sí cambiaron:
contador sin shell, procesos comprobados y movimientos compartidos sin errores
ocultos.[^history]

No se ha usado la biblioteca personal, la Papelera, credenciales ni cargas
remotas. Los originales de las pruebas son sintéticos y viven en temporales.
No se han probado fallos físicos de alimentación, distintos volúmenes reales,
ACL/resource forks, ni bloqueo entre máquinas. La recuperación se acredita en
el sistema local; las operaciones comparan huellas frente a cambios externos,
pero otros editores no participan en el bloqueo del programa.[^core]

ExifTool, fechas vistas en Apple Photos, orientación/calidad visual, perfiles
completos y uploader se verificarán en sus cambios. El orquestador y las pausas
sí están probados; no se presentan los servicios simulados como integraciones
reales superadas ni como implementación de las otras tres propuestas.
Los documentos siguen en `draft`, sin atribuir una aprobación humana.[^scope]

[^tests]: [Suite del núcleo](../../tests/).
[^core]: [Núcleo seguro implementado](nucleo-seguro.md).
[^history]: [Regresiones históricas](auditoria-actual.md).
[^scope]: [Alcance y procedencia](alcance.md).
[^pipeline]: [Proceso reanudable implementado](pipeline-reanudable.md).
