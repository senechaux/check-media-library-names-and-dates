# Núcleo seguro (Python >=3.11)

El paquete `media_library` incorpora TOML validado, inventario, procesos comprobados, manifiesto, journal,
bloqueo, backups y publicación recuperable por evidencia.
Los scripts históricos siguen en `src/`. `run` ya controla etapas, pausas y
reanudación. Fechas, ExifTool y nombres ya tienen servicio real; conversión,
compresión y exportación integral siguen pendientes de integración.

```sh
python3 -m venv .venv-core
. .venv-core/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m pytest -m integration
```

Para fechas automáticas se requieren **ExifTool y FFmpeg/ffprobe** en PATH.
Se ha probado ExifTool 13.40 y FFmpeg 9.0.2. FileCreateDate requiere además
SetFile en macOS; si falta capacidad, queda pendiente. La integración real se
omite con motivo si falta una herramienta; una omisión no prueba compatibilidad.
En macOS con Homebrew, `brew install exiftool ffmpeg` instala las herramientas
del servicio de fechas. HandBrakeCLI es adicional para las integraciones del núcleo.
Si ExifTool está fuera de PATH, los tests aceptan
`MEDIA_LIBRARY_EXIFTOOL=/ruta/exiftool python -m pytest -m integration`.

La suite rápida excluye la marca `integration`. Las integraciones usan medios
sintéticos y herramientas locales; si falta alguna se omiten con su motivo.
Copiar `media-library.example.toml` a `media-library.toml` permite configurar
rutas relativas al TOML, exclusiones, timeout, reserva y herramientas. No poner
rutas personales en Git. La configuración local y `sample/` están excluidos.
Los scripts antiguos mantienen limitaciones y no reciben automáticamente la
protección transaccional del núcleo. El extra `.[legacy]` instala Pillow y progress
si se necesitan sus entradas. No se importa ni ejecuta el main histórico de movimientos.
Los [contratos y compatibilidad](docs/manifest-v1.md) describen el esquema 1.

# Proceso reanudable

Desde cualquier carpeta, con el paquete instalado:

```sh
python -m media_library run --config /ruta/media-library.toml --dry-run
python -m media_library run --config /ruta/media-library.toml --apply
python -m media_library run --config /ruta/media-library.toml --resume <run-id>
```

Sin `--apply`, muestra el plan y pide una aprobación del lote. `--apply` autoriza
operaciones automáticas, sin resolver fechas ni confirmar trabajo manual.
`--dry-run` solo genera inventario/plan/estado/informe y devuelve 2 por plan sin
aplicar: no espera ni prepara copias ni transforma/carga medios. Para aplicar,
crear una ejecución nueva. La reanudación exige el TOML y los adaptadores congelados;
cambiar el alcance o ajustes requiere un plan nuevo.

El ejemplo habilita pausas manuales y deshabilita entrega. `metadata` ya lee y
compara fuentes reales, escribe fechas selectivas con ExifTool y renombra con
backups y recuperación. Normalización, compresión, exportación y auditoría
integral siguen sin sus servicios; confirmar no los completa. Los adaptadores
simulados solo están en tests. Las fechas se publican mediante operaciones del
núcleo; instalación no repite una corrección ya aplicada.

Para recorrer un alcance real limitado a inventario, planificación y conservación,
deshabilitar las etapas pendientes y la revisión/entrega humanas:

```toml
[pipeline.modes]
import_review = "disabled"
metadata = "disabled"
normalize = "disabled"
compression = "disabled"
installation = "auto"
export = "disabled"
audit = "disabled"
delivery = "disabled"
```

En una pausa: `comprobar` revalida, `posponer` conserva el pendiente y `cancelar`
bloquea ese archivo. `decidir authority=metadata timezone=Europe/Madrid` guarda
una decisión explícita validada por el servicio, sin acreditar una corrección de
los campos por sí sola. Sin TTY o con EOF,
persiste `WAITING_USER` y sale con 2; Ctrl+C/cierre de terminal, con 130. Un fallo
operativo devuelve 3; solo completar el alcance sin pendientes devuelve 0.
Tras una caída dura, revisar el propietario y añadir `--recover-stale-lock` al
resume; no desplaza bloqueos activos. No borrar el archivo de bloqueo.

Los informes `plan.json` y `report.json`, el manifiesto y el journal están en
`workspace/run-id/`. La consola muestra sus rutas y la siguiente orden. Una
declaración de carga web se distingue de una verificación API; el comando no
realiza cargas remotas. Véanse la [guía real del proceso](docs/knowledge/pipeline-reanudable.md)
y los [puntos de integración](docs/pipeline-adapters.md), incluidos los tres recorridos
de alcance automático limitado, corrección manual simulada y reanudación sin terminal.

# Fechas y nombres reales

Para ejecutar solo este alcance, habilitar `metadata="auto"` e
`installation="auto"`, y deshabilitar import_review, normalize, compression,
export, audit y delivery en `[pipeline.modes]`. Revisar primero con `--dry-run`.
La configuración temporal puede ser:

```toml
[dates]
policy = "review"
timezone = "Europe/Madrid" # Solo si se ha elegido para este lote.
quicktime_semantics = "unknown"
```

`filename-to-metadata` usa la fecha válida del nombre; `metadata-to-filename`
usa la fuente seleccionada y conserva extensión/descripción. Una fecha parcial
permanece parcial. Conflictos, zona ausente y DST ambiguo requieren decisión:

```text
decidir authority=filename-to-metadata timezone=Europe/Madrid
decidir fold=1
comprobar
```

Las excepciones se configuran en `[dates.files."álbum/ruta-original.JPG"]`.
`source_tag=Keys:CreationDate` permite elegir una fuente discrepante; `date=...`
aporta una fecha conocida explícita, sin inventar partes ausentes. La semántica
QuickTime de lectura solo se declara UTC/local con evidencia. La escritura
QuickTime usa UTC y Keys local con offset y verifica ambos al releer.

Se ha acreditado escritura selectiva JPEG y MP4/MOV, con conservación del
contenido codificado y metadatos ajenos extraídos. Otros formatos o capacidades
no acreditadas conservan pausa manual. `remove_historical=true` retira los dos
prefijos históricos solo después de resolver/verificar; no se añaden prefijos.
`discard_description=true` es una opción explícita. Las fechas del filesystem
se solicitan por separado con `set_file_modify_date` y `set_file_create_date`.

El [detalle de fechas y nombres](docs/knowledge/fechas-nombres.md) documenta
formatos, renombrados con ciclos, idempotencia y límites. **Attributes/Rename y
Apple Photos siguen pendientes de ensayo humano** (tarea 3.3): no se afirma
equivalencia con Apple Photos Brute Force. Los scripts históricos conservan
su comportamiento y no son la entrada del servicio nuevo.

# Documentación y planificación

La [base de conocimiento en formato OKF](docs/knowledge/index.md) documenta el
estado de los scripts. El contenido original que sigue describe el procedimiento
manual y contiene notas históricas; las observaciones de la base de conocimiento
distinguen ese procedimiento del comportamiento efectivo del código.

El [plan de automatización](docs/knowledge/automatizacion.md) propone un comando
único con pausas y reanudación. Los cambios futuros se especifican en
[`openspec/changes/`](openspec/changes/). `safe-execution-core` y `resumable-pipeline`
están implementados y verificados, pendientes de revisión sin archivar; las otras
dos propuestas de vídeo/exportación siguen pendientes. `metadata-and-naming`
tiene implementado lo verificable, con su ensayo humano todavía pendiente.

La [guía de revisión e implementación](docs/knowledge/trabajo-con-agentes.md)
incluye el orden sugerido, decisiones pendientes y skills evaluadas.

# Dependencies
```
brew install ffmpeg mediainfo handbrake gphotos-uploader-cli
pip install -r requirements.txt
```


# PROCESS FOR CATALOGUING PHOTOS AND VIDEOS
1. Check all images from Elena's phone have been uploaded to Dropbox
2. Copy all uploaded photos from Elena's Dropbox and Angel's Dropbox to Angel's Camera uploads in Google Drive
*** pending to create a script to do this step
3. Review manually, remove useless images
4. Run check-filenames.py and rename if needed in a second running using the argument --do_rename.

  ```   
  source .venv/bin/activate

  python3 check-filenames.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2026 --do_rename
  ```

5. ******** TO DO ******** It should check if a video is not mp4. Meanwhile it can be checked doing a search with Finder for files of type Video and ensuring all of them are MP4. Use Permute to convert to mp4.
6. Run check-exif-datetime.py and review logs in './src/logs'. 
  
   ```
   python3 check-exif-datetime.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2026 --do_rename
   ```

   To fix these articles, run again the script with the parametet '--do_rename', it will add the preffix 'diff_datetime' or 'exif_getting_error' to all these files making easy to locate them in Finder.
   Use 'A Better Finder Attributes' to fix metadata datetimes or 'A Bettet Finder Rename' to rename files.

7. Run find-biggest-videos.py and review logs in './src/logs'. Use Handbrake to compress videos.
   
   ```
   python3 find-biggest-videos.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2026
   ```

8. Compress videos in "biggest_videos_to_compress" and output them into "biggest_videos_compressed".
9. Check new sizes are small enough. If they are not then use a smaller size for the reduced video.
10. Set the correct datetime metadata using "A better finder attributes"
11. Run move-biggest-videos.py. It renames the videos adding the suffix " reduced_size", move them to the correct folder, move the original video to "/Users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos videos con bit rate muy alto tmp" and remove the copied videos from folder "biggest_videos_to_compress".
    
    ```
    python3 move-biggest-videos.py
    ```
   
12. Copy photos and videos to gphotos folder:

    ```
    python3 copy-files-to-upload-to-gphotos.py --source ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2026/ --destiny ~/Fotitos_compressed_to_upload_to_gphotos/2026/ --copy_images --copy_videos --video_preset veryfast480p
    ```

13. Run check-exif-datetime.py on "~/Fotitos_compressed_to_upload_to_gphotos/2026/" and review logs in './src/logs'.

    ```
    python3 check-exif-datetime.py --dir ~/Fotitos_compressed_to_upload_to_gphotos/2026/ --do_rename
    ```
    
    To fix these articles, run again the script with the parametet '--do_rename', it will add the preffix 'diff_datetime' to all these files making easy to locate them in Finder.
    
    Use 'A Better Finder Attributes' to fix metadata datetimes or 'A Bettet Finder Rename' to rename files.
14. Run gphotos uploader and backup gphotos uploader folder contents to Google Drive

    ```
    gphotos-uploader-cli push --debug && cp -r ~/.gphotos-uploader-cli/* ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos\ Anexos/gphotos-uploader-cli/
    ```

# TIPS
- How to look for several file names: `find ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/ -type f \( -name "2023-12-07 12.02.23.mp4" -o -name \)`. If you want to add them to A Better Finder Attributes just change the default application to open MP4 files and click in the filenames in Terminal.

# TODO

# DONE
rename ny by ñ
rename folders like 2001-02-03 (4-5) to 2001-02-03 (04-05)
extension to lowercase
extension jpeg to jpg
convert videos to mp4
change EXIF data based on filename for images
change EXIF data based on filename for videos
remove all photos from google photos
remove all albums from google photos using MacroRecorder
encode to reduce size of biggest videos
  mediainfo --Inform="Video;bitrate:%BitRate%b/s duration:%Duration%ms" video.mp4
download folders from Google Drive and compare with local ones
recover original videos from external disk
check exif datetimes again
check "2010-01-16 Cumpleaños Paloma" in external disk
"2017-01-07 Reyes magos Prosperidad" is empty everywhere! check photos and videos in other folders
split script run-files in several scripts
cut photos with gray areas from "2008-10-04 Paracaidas" folder
upload all photos to google photos
  compress images and videos before uploading
investigate on how to rename videos with names like "rduced_size"
investigate on how to rotate images according to their orientation, then resize them and then reupload them
Create script to compress biggest videos and move them to a different folder, and then move the compressed ones to the same folder the biggest one was. Or at least a script to execute the commands to copy and/or move the biggest videos and the compressed one.
Change check-filenames.py to check if a video is not mp4
Move things to Trash `~/.Trash/` instead of deleting them (NOT TESTED)
Estimate date for "Yo de peque"
Estimate date for "Fotos antiguas"
Add person names to photos in "Yo de peque" and "Fotos antiguas"
Merge folders "Yo de peque" and "Fotos antiguas"

# HOW TO USE

## copy-files-to-upload-to-gphotos.py
Creates a thumbnail of the images (the larger size will be 1200px) and a compressed copy of the videos from the source directory to the destiny directory.
### args
  --copy_images: to copy images
  --copy_videos --video_preset veryfast480p: to compress and copy videos

```
python3 copy-files-to-upload-to-gphotos.py --source "/users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos/2023/" --destiny "/users/angel/Fotitos_compressed_to_upload_to_gphotos/2023/" --copy_images --copy_videos --video_preset veryfast480p
```

## rename-files.py
Rename files attending to regexp rules. Convert the extension to lowercase and rename 'jpeg' extensions to 'jpg'.

### args
  --do_rename: Do rename files, instead of just logging changes

```
python3 rename-files.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023
/```

## find-biggest-videos.py
Find and log to an output file biggest videos in a folder. Ignores videos which name contains "reduced_video" since they have been already reduced.

```
python3 find-biggest-videos.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023
/```

## compress-non-mp4-videos.py
DO NOT USE. Not needed now.

## check-filenames.py
Check all files recursively to find those that do not match the desired name structure. Rename to a correct format.

### args
  --do_rename: Do rename files, instead of just logging changes

```
python3 check-filenames.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023
/```

## check-exif-datetime.py
Check all files recursively and check if the datetime in their name matches the datetime in Exif data

### args
  --do_rename: Do rename files, instead of just logging changes

```
python3 check-exif-datetime.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023
/```

Fix
===

1973-1999 ******************************************
=========
678 items, totalling 1,0 GB
677 items, totalling 769,1 MB

2000
====
118 items, totalling 68,7 MB
117 items, totalling 12,7 MB

2001
====
29 items, totalling 24,6 MB
29 items, totalling 3,5 MB

2002
====
199 items, totalling 2,9 GB
199 items, totalling 2,2 GB

2003
====
1.771 items, totalling 2,0 GB
1.750 items, totalling 418,7 MB

2004
====
3.412 items, totalling 4,9 GB
3.333 items, totalling 1,3 GB

2005
====
840 items, totalling 1,1 GB
837 items, totalling 381,0 MB

2006
====
3.168 items, totalling 3,9 GB
3.161 items, totalling 1,1 GB

2007
====
5.872 items, totalling 17,8 GB
5.872 items, totalling 6,4 GB

2008
====
2.515 items, totalling 7,0 GB
2.488 items, totalling 2,1 GB

2009
====
1.485 items, totalling 3,8 GB
1.484 items, totalling 1,3 GB

2010
====
1.794 items, totalling 5,7 GB
1.794 items, totalling 1,5 GB

2011
====
2.197 items, totalling 8,1 GB
2.197 items, totalling 2,3 GB

2012
====
1.492 items, totalling 5,5 GB
1.492 items, totalling 1,1 GB

2013
====
8.130 items, totalling 38,6 GB
8.130 items, totalling 4,9 GB

2014
====
2.021 items, totalling 10,4 GB
2.022 items, totalling 1,9 GB

2015
====
3.273 items, totalling 11,7 GB
3.273 items, totalling 1,5 GB

2016
====
2.849 items, totalling 14,2 GB
2.849 items, totalling 2,4 GB

2017
====
3.663 items, totalling 23,6 GB
3.662 items, totalling 4,4 GB

2018
====
3.253 items, totalling 22,6 GB
3.253 items, totalling 4,7 GB

2019
====
2.824 items, totalling 29,2 GB
2.824 items, totalling 2,9 GB

2020
====
2.962 items, totalling 39,3 GB
2.957 items, totalling 4,0 GB

2021
====
2.969 items, totalling 43,6 GB
2.969 items, totalling 5,7 GB

2022
====
3.227 items, totalling 42,1 GB
3.227 items, totalling 5,6 GB

2023
====
1.884 items, totalling 18,8 GB
1.884 items, totalling 2,3 GB
