---
type: Reference
title: Auditoría actual de nombres y fechas
description: Contratos efectivos y limitaciones de check-filenames, check-exif-datetime y common_functions.
tags: [actual, nombres, exif, fechas]
status: draft
x_snapshot_commit: bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c
sources:
  - id: names
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/check-filenames.py
  - id: dates
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/check-exif-datetime.py
  - id: common
    resource: https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/common_functions.py
---
# check-filenames.py

`main()` recibe `--dir` obligatorio y `--do_rename` opcional. Crea
`logs/<YYYYmmdd_HHMMSS>_check_filenames/` y llama a `check_file_names()`.
Sin `--do_rename` escribe logs, pero no renombra medios.[^names]

- Nombre admitido: `YYYY-MM-DD HH.MM.SS[ texto].ext`. Extensiones sensibles a
  mayúsculas: `jpg|JPG|jpeg|png|gif|bmp|HEIC|mp4`.
- Clasifica nombres no válidos en 18 patrones, índices 0–17, y un resto.
  Reconstruye fechas y conserva parte del texto. Si falta día usa `01`; si
  falta hora usa `00.00.00`; si falta mes usa enero.
- Los patrones 0 y 17 no construyen un nombre de salida. El patrón 16, año
  seguido de texto, sí lo construye pero queda fuera de la lista que permite
  imprimir/aplicar renombrados. Solo se registra la propuesta.
- No cambia de forma general las extensiones a minúsculas ni `jpeg` a `jpg`.
  Un nombre ya válido con `.JPG` o `.jpeg` se omite.
- No verifica fechas con calendario al admitir nombres: permite día `00` y
  horas `24`–`29`. No detecta colisiones antes de `os.rename()`.
- Ignora `.DS_Store`, `.localized` y rutas que contengan ciertos nombres
  personales, `En proceso`, `Camera Uploads` o `Capturas de pantalla`.
  Las reglas de exclusión no son idénticas en los demás scripts.
- Genera `invalid_case_00.log` … `invalid_case_17.log` solo si tienen entradas
  y `invalid_files_rest_of_cases.log`. No modifica metadatos.[^names]

# check-exif-datetime.py

`main()` recibe `--dir` y `--do_rename`; crea otra carpeta con sufijo
`_check_filenames`, indistinguible por ese sufijo de la auditoría de nombres.
Llama primero a imágenes y después a vídeos. El texto de ayuda de
`--do_rename` dice lo contrario de lo que hace.[^dates]

## Imágenes

Aunque el patrón declara JPG, PNG, GIF y BMP, los tres últimos se excluyen
antes de procesar: se auditan efectivamente `.jpg` en minúsculas con nombre
canónico. JPG en mayúsculas, JPEG y HEIC no se auditan. Pillow obtiene
`DateTimeOriginal` y `DateTimeDigitized` con `_getexif()`, pero solo compara
`DateTimeOriginal` con el nombre, segundo a segundo y sin zona horaria.

Si difieren, registra `exif_date_different_from_filename_date.log` y puede
añadir `diff_datetime `. Si faltan EXIF, la fecha es vacía/inválida o sucede
cualquier excepción, registra `exif_getting_error.log` y puede añadir
`exif_getting_error `. Una excepción de renombrado también cae en este bloque.
No escribe EXIF y no quita después los prefijos. Una ejecución posterior
omite los archivos con esos prefijos porque no cumplen el patrón.[^dates]

## Vídeos

Procesa `.mp4` y `.mov` en minúsculas con nombre canónico. Cuenta MP4 para
la barra de progreso, aunque también procesa MOV. `get_video_metadata()`
solo consulta tags del contenedor con `ffprobe -show_entries format_tags`.
Recoge `date` y `com.apple.quicktime.creationdate` para los logs, pero compara
únicamente `creation_time` con el nombre al que añade artificialmente `Z`.
Exige el formato `%Y-%m-%dT%H:%M:%S.%fZ`; valores ISO con offset o sin
fracción pueden interrumpir el proceso. No existe una captura general de
errores por vídeo.[^dates][^common]

| Condición | Resultado actual |
| --- | --- |
| Sin metadatos recuperables | `videos_diff_no_metadata.log`, sin prefijo. |
| Hay tags pero falta `creation_time` | `videos_no_tag_creation_time.log`, prefijo `diff_datetime ` si se pide renombrar. |
| `floor(abs(diferencia en horas))` vale 1 o 2 | `videos_diff_OK_because_of_timezone.log`, sin demostrar la zona. |
| Cualquier otra diferencia, incluida cero | `videos_diff_KO.log`, prefijo `diff_datetime ` si se pide renombrar. |

Esto acepta diferencias desde 1 h hasta menos de 3 h como zona horaria y
rechaza coincidencias exactas. El patrón `equal_with_different_timezone_to_change`
está declarado pero no se usa.[^dates]

# common_functions.py

`count_files_with_the_extension()` ejecuta `find | wc -l` mediante shell,
devuelve texto en éxito y entero `0` en error. Los nombres con apóstrofos
pueden romper el comando. `get_video_metadata()` usa una lista de argumentos
para ffprobe, devuelve tags o `None` si ffprobe falla, pero presupone las
claves JSON `format.tags`; su ausencia provoca `KeyError`.

`move_file()`/`move_folder()` capturan errores y solo imprimen mensajes,
sin devolver un estado de éxito. `remove_file()`/`remove_folder()` los usan
para mover a `~/.Trash/`. No garantizan un destino sin colisiones ni que
el llamador se detenga si el movimiento falla. Las otras funciones crean
directorios, ordenan logs y convierten milisegundos.[^common]

# Evidencia reproducida durante la revisión

El 2026-11-13 se importaron los módulos con `sys.dont_write_bytecode=True`,
usando directorios temporales y sustituyendo la consulta de metadatos y el
contador por valores simulados. No hubo lectura de medios personales.

1. Nombre `2026-11-10 18.59.08.mp4`, tag `2026-11-10T18:59:08.000000Z`:
   generó `videos_diff_KO.log`.
2. Mismo nombre, tag `2026-11-10T21:58:08.000000Z`: generó
   `videos_diff_OK_because_of_timezone.log` con una diferencia de 2 h 59 min.
3. `2004 vacaciones.jpg` y `do_rename=True`: conservó el nombre, aunque
   el patrón 16 produjo una propuesta en el log.

Estas comprobaciones confirman esos tres comportamientos; no validan
lectura/escritura EXIF real, codecs ni compatibilidad con aplicaciones.

[^names]: [check-filenames.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/check-filenames.py).
[^dates]: [check-exif-datetime.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/check-exif-datetime.py).
[^common]: [common_functions.py](https://github.com/senechaux/check-media-library-names-and-dates/blob/bf3554fab9a04414c3f369ecc4a9fc2dcdbb297c/src/common_functions.py).
