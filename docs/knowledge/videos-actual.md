---
type: Reference
title: Selección y sustitución actual de vídeos
description: Qué hacen find-biggest-videos y move-biggest-videos y cómo comparten los archivos temporales.
tags: [actual, video, compresion, archivos]
status: draft
x_snapshot_commit: bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c
sources:
  - id: find
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/find-biggest-videos.py
  - id: move
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/move-biggest-videos.py
  - id: common
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/common_functions.py
---
# find-biggest-videos.py

`main()` acepta `--dir` obligatorio y no ofrece modo de simulación. Crea
`logs/<fecha>_biggest_videos/`, obtiene la lista, crea las dos carpetas de trabajo,
copia los vídeos seleccionados y escribe archivos de correspondencia.[^find]

| Aspecto | Comportamiento actual |
| --- | --- |
| Selección | Nombre que empiece por cuatro dígitos y guion; extensión minúscula `mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv`. |
| Exclusión | `.DS_Store`, `.localized` y cualquier nombre que contenga `reduced_size`; no aplica las exclusiones personales de la auditoría. |
| Umbral | `floor(bytes / 1000 / 1000) >= 50`: 50.000.000 bytes o más. No existe umbral de bitrate. |
| Inspección | `mediainfo` obtiene bitrate, duración, ancho y alto a través de shell. |
| Logs | `biggest_videos_by_size.log` y `biggest_videos_by_bitrate.log`, ordenados como texto descendente. |
| Copia | `shutil.copy2()` a `../biggest_videos_to_compress/<basename>` si ese nombre no existe. |
| Correspondencia | `<basename>_full_path.txt` en ambas carpetas contiene la ruta original recibida, que puede ser relativa. |
| Comprimidos | Crea `../biggest_videos_compressed/`, pero no comprime ningún vídeo. |

Las rutas dependen del directorio de ejecución. Dos vídeos con el mismo
basename en álbumes diferentes comparten destino y archivo de correspondencia:
el segundo se omite silenciosamente. Reutilizar las carpetas puede reutilizar
copias y rutas antiguas. El sort textual con anchura mínima no es un orden
numérico fiable para todos los tamaños/bitrates. Bitrate vacío o metadatos
inesperados pueden fallar al convertir a entero; si MediaInfo falla,
`width_x_height` puede quedar sin asignar.[^find]

# move-biggest-videos.py

No admite rutas ni opciones de simulación: usa las carpetas `../biggest_videos_*`
y una ruta absoluta personal para archivar originales, terminada en
`Fotitos videos con bit rate muy alto tmp`. No crea esa carpeta de archivo.[^move]

El orden real de `main()` es:

1. `get_video_list(False)` recoge basenames MP4 que empiecen por año y no
   contengan `reduced_size`, incluso recorriendo subcarpetas.
2. `rename_videos_compressed()` añade ` reduced_size` antes de la extensión.
3. Vuelve a listar, ahora con `get_video_list(True)`.
4. `move_videos_original()` lee cada `_full_path.txt` y mueve el original
   a la carpeta de archivo **antes** de instalar el comprimido.
5. `move_videos_compressed()` lee la misma correspondencia y mueve el MP4
   a la carpeta original, salvo que ya exista ese nombre de salida.
6. Lista todos los MP4 aún no reducidos en `biggest_videos_to_compress` y
   los manda a la Papelera, aunque no tengan comprimido validado.
7. Agrupa todos los `_full_path.txt` de ambas carpetas en carpetas fechadas
   y las manda a la Papelera. Finalmente imprime instrucciones de backup y
   movimiento manual en Google Drive web.[^move]

`get_video_list()` devuelve solo nombres, pero el resto del código presupone
que están directamente bajo la carpeta raíz; las subcarpetas no se resuelven
correctamente. Solo se aceptan comprimidos MP4, aunque la selección inicial
admite otros contenedores. La correspondencia depende de conservar también
la extensión del basename original, por lo que convertir MOV → MP4 no encaja
en el protocolo actual sin cambios.[^move]

# Límites de integridad

No se comprueban código de salida del codificador, decodificación, duración,
tamaño menor, orientación, pistas ni fechas antes de apartar el original.
Los archivos de correspondencia son texto sin huella del original. El archivo
de originales aplana todos los álbumes y puede colisionar por basename.

Hay comprobaciones parciales de duplicados que imprimen errores y continúan;
las fases siguientes siguen usando la lista completa. No hay transacción ni
rollback. Una colisión, interrupción o copia incompleta puede dejar originales
apartados y resultados sin instalar. Los helpers de Papelera ocultan errores
al llamador, por lo que la limpieza tampoco tiene una señal fiable de éxito.[^move][^common]

Estos hechos proceden de lectura estática. No se han movido vídeos ni se ha
probado la Papelera. La sustitución segura se propone antes de automatizar
este flujo en el [plan de automatización](automatizacion.md).

[^find]: [find-biggest-videos.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/find-biggest-videos.py).
[^move]: [move-biggest-videos.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/move-biggest-videos.py).
[^common]: [common_functions.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/common_functions.py).
