---
type: Reference
title: Exportación y utilidades actuales
description: Copias para Google Photos, lanzador Bash, recuentos y volcado de estructura.
tags: [actual, exportacion, google-photos, inventario]
status: draft
x_snapshot_commit: bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c
sources:
  - id: export
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/copy-files-to-upload-to-gphotos.py
  - id: shell
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/copy-files-to-upload-to-gphotos-folders.sh
  - id: count
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/find-and-count.py
  - id: dump
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/files-and-folders-structure-dumper.py
---
# copy-files-to-upload-to-gphotos.py

Recibe `--source`, `--destiny`, `--copy_images`, `--copy_videos` y
`--video_preset`. Las rutas son obligatorias; las dos selecciones son opcionales.
Sin ninguna selección crea carpetas pero no exporta medios. El preset se
valida al llegar a vídeos, después de haber podido procesar imágenes.[^export]

| Función | Comportamiento actual |
| --- | --- |
| `find_and_copy_images()` | Recorre JPG minúsculos con nombre que empiece por año-guion; conserva la jerarquía mediante reemplazo textual de rutas; omite todo destino existente. |
| `resize_image()` | Reduce el lado mayor a 1200 px sin ampliar; guarda JPEG conservando el bloque EXIF existente. |
| `find_and_copy_videos()` | Recorre MP4 minúsculos con nombre que empiece por año-guion; mismo esquema de rutas y omisión. |
| `resize_video()` | Obtiene ancho/alto con MediaInfo y los pasa a HandBrakeCLI junto al preset; transmite salida a consola. |
| Temporales | `<destiny>/tmp/<basename>` compartido por todos los álbumes; después se mueve al destino. |
| Logs | `./logs/logs_copy_to_upload_to_gphotos/`, nombres fijos, escritura acumulativa sin identificador de ejecución. |

Presets actuales: `veryfast480p` → `Very Fast 480p30`, `social480p` →
`Social 50 MB 10 Minutes 480p30` y `social360p` →
`Social 8 MB 3 Minutes 360p30`. No ofrece `Fast 720p30` para esta exportación.
Pasar las dimensiones originales como `--width` y `--height` no garantiza
respetar el límite de resolución anunciado por el preset.[^export]

La imagen exige `img.info['exif']`: si no hay EXIF, captura el error e imprime
un mensaje, y el llamador intenta mover de todos modos el temporal. No aplica
`ImageOps.exif_transpose()` ni normaliza Orientation. No hay política explícita
de ICC o imágenes con otros modos de color.

HandBrake se lanza con `Popen(shell=True)` sin comprobar `returncode`.
Un estado no cero no lanza el `CalledProcessError` que captura el código.
Solo comprueba existencia y compara tamaños; un archivo parcial puede pasar.
Aunque el resultado sea mayor, el llamador intenta moverlo igualmente.
No restaura ni verifica fechas después de comprimir. Un destino existente
se considera terminado sin comprobar integridad, cambios del origen o perfil.
La carpeta `tmp` bajo un destino incluido en el origen puede recorrerse como
entrada: no hay validación de solapamiento de rutas.[^export]

# copy-files-to-upload-to-gphotos-folders.sh

Itera los años 2000–2023 fijados en un array. Usa rutas personales absolutas
y llama al exportador solo con `--copy_images`. La opción de vídeos está
comentada. No acepta configuración, no descubre años nuevos y no detiene el
bucle expresamente si una llamada falla. Requiere ejecutarse desde `src/`.[^shell]

# find-and-count.py

`main()` recibe `--dir` y `--include_dir`, crea
`logs/<fecha>_find_and_count/` y llama a `find_and_count_files()`.
Cuenta y suma bytes por año y extensión para nombres con prefijo año-guion:
imágenes `jpg|jpeg|png|gif|bmp` y nueve extensiones de vídeo. Clasifica el
resto de archivos con extensión como «otros»; archivos sin punto se omiten.
No aplica las exclusiones de carpetas de la auditoría.[^count]

Genera `video_names.log`, `image_names.log`, `any_file_names.log` cuando hay
entradas y `file_counts.log`. Tamaños en MiB aunque la etiqueta diga MB.
Los porcentajes por año dividen el total de vídeos por la cantidad de MP4,
y el total de imágenes por la de JPG, no por el total de cada categoría.
Con AVI pero sin MP4, o PNG pero sin JPG, puede producir `KeyError`.
No es un inventario independiente del formato de nombres.[^count]

# files-and-folders-structure-dumper.py

`main()` recibe `--dir`, crea una carpeta de logs que la función no usa y
llama a `check_photos_uploaded_to_gphotos()`. Pese al nombre de la función,
no consulta Google Photos: vuelca únicamente el árbol local.

Escribe `albums_in_folder_with_counter.json` y
`albums_in_folder_with_images.json` en el directorio de ejecución,
sobrescribiendo los anteriores. Presupone `<raíz>/<año>/<álbum>/<archivo>`
al usar los índices 1 y 2 de la ruta; archivos a menor profundidad pueden
provocar `IndexError` y subcarpetas más profundas se agrupan bajo el álbum.
El primer archivo inicia el contador en cero: un álbum de N archivos se
cuenta como N−1. Aplica una lista de exclusiones similar a EXIF.[^dump]

# Divergencias del README

El README menciona `rename-files.py` y `compress-non-mp4-videos.py`, ausentes
del repositorio. La lista DONE contiene tareas históricas que no prueban una
capacidad de los scripts actuales. `find-biggest-videos.py` excluye
`reduced_size`, aunque una sección del README diga `reduced_video`.
Las cifras históricas de archivos no son resultados de esta revisión.

[^export]: [Exportador](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/copy-files-to-upload-to-gphotos.py).
[^shell]: [Lanzador Bash](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/copy-files-to-upload-to-gphotos-folders.sh).
[^count]: [Recuentos](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/find-and-count.py).
[^dump]: [Volcado de estructura](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/files-and-folders-structure-dumper.py).
