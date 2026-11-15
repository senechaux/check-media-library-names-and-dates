---
type: Reference
title: Núcleo seguro implementado
description: Configuración, inventario y operaciones locales interrumpibles y recuperables.
tags: [actual, python, seguridad, recuperacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: code
    resource: ../../src/media_library/
    title: Paquete media_library
  - id: contract
    resource: ../manifest-v1.md
    title: Contratos y compatibilidad del esquema 1
  - id: tests
    resource: ../../tests/
    title: Suite rápida e integraciones sintéticas
---
# Capacidades actuales

`safe-execution-core` implementa el paquete instalable `media_library` para
Python >=3.11, usando biblioteca estándar en ejecución. Se mantienen las entradas
históricas; el núcleo no importa sus `main()` ni ejecuta movimientos heredados.
El cambio permanece en `openspec/changes/` para revisión, sin archivar.[^code]

| Área | Comportamiento implementado |
| --- | --- |
| Configuración | TOML estricto, rutas relativas al TOML, orígenes/destinos disjuntos tras resolver enlaces, exclusiones, timeout y reserva. |
| Preflight | Comprueba permisos, espacio agregado por volumen y versiones/capacidades declaradas; no crea destinos. |
| Inventario | Recorre cualquier profundidad; admite nombres irregulares y mayúsculas; reconoce firmas de imagen y contenedor/codec con ffprobe para otros candidatos. |
| Incidencias | Archivos no soportados/ilegibles, FIFOs, symlinks y colisiones se reportan expresamente; no significan éxito total. |
| Identidad | ID propio por entrada, incluso con bytes idénticos; conserva ruta original e historial tras renombrar. |
| Procesos | Listas de argumentos sin shell, timeout, código de salida y diagnóstico; termina el grupo en timeout/interrupción. |
| Estado | Manifiesto JSON versión 1, journal sincronizado antes del snapshot atómico y bloqueo por origen resuelto. |
| Operaciones | Preparar candidato, verificarlo con validador de etapa, planificar replace/rename/export, respaldar originales por hash y publicar localmente. |
| Recuperación | Comparar entrada/candidato/destino/backup y continuar o restaurar explícitamente, sin repetir una publicación acreditada. |

Las rutas temporales usan `workspace/run_id/file_id/`. El primer original queda
en `archive/run_id/ruta-original`; las revisiones posteriores usan una subruta
por operación. Dos álbumes con el mismo basename tienen operaciones y backups
distintos. Las equivalencias de mayúsculas/Unicode se rechazan conservadoramente
como conflictos antes de escribir; no se aplana ni cambia silenciosamente la
jerarquía. Los `_full_path.txt` históricos se inventarían como pendientes/no
soportados, sin convertirlos en instrucciones de movimiento.[^contract]

# Uso y recuperación

Instalar con `python -m pip install -e '.[dev]'` dentro de un entorno virtual.
El [README](../../README.md) contiene los comandos y el ejemplo TOML no incluye
rutas personales. `preflight(config)` e `inventory(config)` permiten inspección
sin modificar medios; las escrituras de estado empiezan al crear `RunStore`.
La API y sus estados están descritos en [el contrato](../manifest-v1.md).

Adquirir `SourceLock` antes de crear o cargar una ejecución. La exclusión usa
dispositivo/inode del origen, también para alias de mayúsculas/Unicode admitidos
por el volumen. Un descriptor mantiene esa identidad abierta; sustituir el
directorio invalida el bloqueo antes de usar el almacén. Se conserva además el
lock antiguo de la ruta para reconocer sus propietarios. Cerrar versiones
anteriores al actualizar: no conocen el nuevo lock de los otros alias.
Tras una caída dura,
revisar el propietario y pedir `recover_stale=True`: un bloqueo activo nunca
se fuerza. Cargar con `RunStore.load`, consultar `SafeExecutor.inspect` y elegir
`execute` para continuar o `restore` para restaurar cuando la evidencia lo permita.
La restauración conserva también el resultado sustituido. Si hay contenido
externo desconocido, detener y replantear. El fallo al persistir exige recargar
el estado; no se permite seguir escribiendo con un almacén incierto.[^contract]

# Límites de esta entrega

El núcleo ofrece API, consumida ya por el [proceso reanudable](pipeline-reanudable.md)
con `python -m media_library run`, pausas e informes. Las
[fechas y nombres](fechas-nombres.md) ya usan un servicio real sobre estos contratos.
La [normalización y compresión de vídeo](video-validado.md) usa estos contratos,
incluida `substitute`: publica el derivado con backup y retira después su original.
[Exportación y auditoría](exportacion-entrega.md) ya consumen estos contratos.
La entrega tiene protocolo optativo y backup, con transporte remoto simulado en
pruebas y compatibilidad de gphotos pendiente. `export` sigue siendo la primitiva
que publica candidatos; renovar uno propio conserva el destino anterior por hash.
Las firmas de imagen clasifican contenido, sin certificar que una imagen completa
sea decodificable: esa validación corresponde al consumidor de `prepare`.

El bloqueo es Unix local, por usuario; no coordina otros equipos ni aplicaciones
externas. Evitar editores/sincronizadores escribiendo durante una aplicación:
las precondiciones se comprueban inmediatamente antes de publicar, pero no existe
compare-and-swap de archivos en la biblioteca estándar frente a esos escritores.
Se requiere soporte de hardlinks y fsync; no se promete atomicidad entre volúmenes.
Los backups conservan bytes, modo y atime/mtime; el hash no acredita ACL, atributos
extendidos ni resource forks. No hay limpieza global ni retención automática.
Los enlaces temporales privados de publicación se retiran tras verificarla,
antes de registrar el stat final; candidatos y backups permanecen conservados.

Las integraciones acreditan compatibilidad básica del núcleo con ffprobe/FFmpeg
y HandBrake sobre medios sintéticos, sin aprobar perfiles ni calidad visual.
Las pruebas de ExifTool y del perfil de vídeo están en sus fichas. La recuperación
de vídeo se ha probado entre el volumen local y uno HFS+ sintético montado desde
una imagen temporal. No se ha probado sobre biblioteca personal, cuentas remotas
ni discos físicos distintos. Véase [verificación](verificacion.md).[^tests]

[^code]: [Código del núcleo](../../src/media_library/).
[^contract]: [Contrato del esquema y operaciones](../manifest-v1.md).
[^tests]: [Pruebas sintéticas](../../tests/).
