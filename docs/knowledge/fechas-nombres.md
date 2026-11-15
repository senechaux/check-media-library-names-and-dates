---
type: Reference
title: Fechas y nombres implementados
description: Lectura, decisiones, ExifTool selectivo, renombrados y límites de compatibilidad.
tags: [actual, fechas, nombres, exiftool, recuperacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: dates
    resource: ../../src/media_library/capture_dates.py
  - id: service
    resource: ../../src/media_library/metadata_stage.py
  - id: writer
    resource: ../../src/media_library/exiftool.py
  - id: names
    resource: ../../src/media_library/naming.py
  - id: integration
    resource: ../../tests/test_metadata_pipeline_integration.py
  - id: quicktime
    resource: https://github.com/exiftool/exiftool/blob/13.40/html/TagNames/QuickTime.html
  - id: exif
    resource: https://github.com/exiftool/exiftool/blob/13.40/html/TagNames/EXIF.html
---
# Alcance implementado

La etapa `metadata` del comando `run` usa ahora un servicio real para leer fechas,
compararlas, resolver decisiones explícitas, escribir campos seleccionados y
renombrar. Reutiliza StageResult, copias verificadas, backups, bloqueo, manifiesto
y journal. Las otras etapas de conversión, compresión, exportación y auditoría
integral siguen pendientes. `metadata-and-naming` permanece sin archivar y con
la tarea 3.3 pendiente de ensayo humano con las apps.[^service]

`CaptureDate` conserva valor original, fuente/tag, valor normalizado, precisión,
offset/zona, fold, confianza, suposiciones e incidencia. Admite año, mes, día y
timestamps completos con segundos/fracciones; valida calendario e ISO con Z u
offset, además del formato EXIF. Una fecha parcial no se convierte en enero/día
1/medianoche. Las fracciones se conservan aunque superen seis dígitos; el nombre
canónico tiene segundos y la comparación usa la precisión común.[^dates]

Las coincidencias son correctas; una diferencia de 2 h 59 min sigue siendo
discrepancia salvo que los offsets/zonas acreditados prueben el mismo instante.
No se añade Z a una hora local ni se elige la zona por el reloj del ordenador.
La zona IANA elegida se registra por lote/archivo. Una hora DST inexistente
requiere otra fecha explícita; una repetida requiere fold u offset. Las fuentes
válidas contradictorias requieren selección, incluso si existe prioridad.

# Lectura y decisiones

ExifTool lee JSON con grupos e instancias (`-G1:4 -a`). Se conservan las fechas
raw y los diagnósticos de cada fuente. Imágenes: DateTimeOriginal y offsets;
CreateDate solo como fallback automático si se habilita. Vídeos: Keys:CreationDate
con offset y fechas QuickTime/pistas con semántica declarada. La lectura usa
QuickTimeUTC=0 para evitar conversiones por la zona del host. `quicktime_semantics`
es `unknown` por defecto; elegir `utc` o `local` exige conocer la procedencia.
Las fechas del sistema son evidencia suplementaria y solo se eligen como fuente
si se indica su tag explícitamente.[^quicktime]

La tabla `[dates]` admite `policy = "review"` (predeterminada),
`filename-to-metadata` y `metadata-to-filename`. `timezone`, `fold`, `offset` y
`source_tag` resuelven la elección; `date` aporta una fecha conocida explícita con
procedencia de usuario. No autoriza inventar precisión ausente. La fecha explícita
también requiere elegir una dirección antes de escribir. La tabla
`[dates.files."álbum/ruta-original.JPG"]` permite excepciones por archivo. Esa
ruta original y el ID permanecen estables al reanudar; para una nueva ejecución,
las excepciones deben referirse a sus rutas de entrada actuales.

En una pausa se puede guardar, por ejemplo:

```text
decidir authority=filename-to-metadata timezone=Europe/Madrid
decidir fold=1
decidir source_tag=Keys:CreationDate
decidir date=1987-07-10T15:16:17+02:00
comprobar
```

Cada elección queda persistida. `--apply` no resuelve conflictos. En modo auto,
tras elegir autoridad se vuelve a auditar y se aplica el servicio real. En modo
manual o ante una capacidad ausente, las apps actúan sobre copias por ID; la
confirmación dispara el validador y no acredita éxito por sí sola. Una copia
renombrada se asocia por huella única o `output` explícito dentro de su directorio;
no se adivina entre homónimos. Falta de herramienta o prueba técnica conserva
la pausa. Un fallo operativo por archivo conserva su diagnóstico y permite
auditar los demás.

# Escritura y conservación verificadas

| Formato | Campos de fecha automáticos |
| --- | --- |
| JPEG | ExifIFD:DateTimeOriginal, ExifIFD:CreateDate (DateTimeDigitized), offsets Original/Digitized y subseconds cuando existen o se seleccionan. |
| MP4/MOV | QuickTime:CreateDate y fechas de creación de las pistas en UTC; Keys:CreationDate local con offset explícito. M4V está admitido por el servicio, sin fixture propio en esta verificación. |
| Otros tipos o fechas duplicadas ambiguas | Lectura/renombrado cuando la fuente sea utilizable; escritura automática no acreditada, con incidencia/pausa manual. |

No se escribe AllDates ni All:All. `metadata-to-filename` conserva los tags;
`filename-to-metadata` conserva el nombre salvo una acción explícita adicional.
Las fracciones preexistentes se conservan al cambiar segundos. Cada campo
objetivo se relee; una escritura parcial no se publica. Se comparan los metadatos
ajenos extraídos (incluidas instancias duplicadas), el contenido codificado JPEG
o los paquetes/extradata del vídeo y su legibilidad mediante FFmpeg/ffprobe.
Los originales quedan en backups por hash antes de publicar.[^writer][^exif]

`set_file_modify_date` y `set_file_create_date` son opciones separadas, falsas
por defecto. Se verifican en la ruta final, también después de renombrar.
FileCreateDate requiere macOS, birthtime y SetFile, con precisión de segundos;
la falta de capacidad deja una pausa y no equivale a éxito. No se promete
preservar ACL/resource forks ni atributos del filesystem no solicitados, más
allá de las garantías del núcleo.

# Nombres, interrupciones e idempotencia

Se mantiene extensión y descripción; `discard_description=true` permite
descartarla explícitamente. Se reservan todos los destinos, con sufijos estables
` (2)`, ` (3)` por ruta original y comparación conservadora de mayúsculas/Unicode.
Los ciclos y cambios de mayúsculas usan dos pasos con temporales por ID dentro
del origen. La intención de todo el lote se registra antes de retirar nombres.
Cada paso usa operaciones seguras con backup, huella y publicación exclusiva.
La recuperación acredita operaciones, sin repetir una escritura ExifTool ya
preparada/verificada ni una publicación completada.[^names]

Los prefijos `diff_datetime ` y `exif_getting_error ` se auditan y se conservan
por defecto. `remove_historical=true` solo los retira después de resolver la
incidencia y verificar el contenido/campos correspondientes. No se añaden nuevos
prefijos. Una segunda ejecución sobre los resultados corregidos no propone más
escrituras o renombrados con la misma política. Los enlaces temporales privados
de publicación se retiran al acreditarla, antes de registrar la huella final;
así no vuelven a inventariarse como medios. No hay limpieza global: candidatos,
backups y restos de ejecuciones antiguas se conservan para revisión.

# Requisitos, evidencia y comprobación humana pendiente

Se han probado ExifTool **13.40**, FFmpeg/ffprobe **9.0.2** y Python **3.12.15**.
Instalar ExifTool y FFmpeg/ffprobe en PATH; si se fija ExifTool en `[tools.exiftool]`,
usar `version_args=["-ver"]`. Una herramienta declarada en tools es requerida por
preflight; sin declaración y ausente, metadata informa la limitación en una pausa.
SetFile es adicional para la fecha de creación macOS. La suite usa medios mínimos
sintéticos en temporales; el binario de ExifTool de esta sesión se descargó del
repositorio oficial a `/private/tmp`, sin instalación global.

Las 18 integraciones nuevas acreditan JPEG, MP4/MOV, fracciones, ambas direcciones,
FileModifyDate/FileCreateDate en el host probado, ciclos, colisiones, corrección
manual, DST e interrupciones. Se suman a las 2 integraciones reales existentes.
No acreditan escritura universal PNG/GIF/HEIC ni los servicios de las otras
propuestas. Véase [verificación](verificacion.md).[^integration]

La tarea **3.3 sigue pendiente**: no se han abierto Attributes, Rename ni Apple
Photos. Para ensayarla, usar copias locales no personales y una biblioteca nueva
de Photos aislada; registrar versiones de apps/macOS, zona de visualización y
ajustes de las capturas. Comparar todos los tags antes/después de cada app y del
servicio, nombres, contenido y fechas del filesystem; después comprobar la fecha
mostrada por Photos para JPEG y MP4/MOV, incluyendo verano/invierno. El modo
Apple Photos Brute Force no tiene un conjunto de tags demostrado aquí. Si difiere,
conservar el recorrido manual y no declarar equivalencia. El resultado requiere
revisión humana y no se ha sustituido por tests simulados.

[^dates]: [Modelo y comparación](../../src/media_library/capture_dates.py).
[^service]: [Servicio del pipeline](../../src/media_library/metadata_stage.py).
[^writer]: [Escritor y verificación](../../src/media_library/exiftool.py).
[^names]: [Reserva y recuperación de lotes](../../src/media_library/naming.py).
[^integration]: [Integraciones reales del pipeline](../../tests/test_metadata_pipeline_integration.py).
[^quicktime]: [Semántica QuickTime de ExifTool 13.40](https://github.com/exiftool/exiftool/blob/13.40/html/TagNames/QuickTime.html).
[^exif]: [Tags EXIF de ExifTool 13.40](https://github.com/exiftool/exiftool/blob/13.40/html/TagNames/EXIF.html).
