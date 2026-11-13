---
type: Reference
title: Ajustes externos y equivalencias propuestas
description: Transcripción de las tres capturas y límites de la automatización con ExifTool y HandBrakeCLI.
tags: [propuesto, exiftool, handbrake, capturas]
status: draft
sources:
  - id: screenshots
    resource: "Tres capturas adjuntas al encargo del usuario del 2026-11-13"
    title: Attributes, Rename y HandBrake
  - id: quicktime
    resource: https://github.com/exiftool/exiftool/blob/master/html/TagNames/QuickTime.html
  - id: filesystem
    resource: https://github.com/exiftool/exiftool/blob/master/html/TagNames/Extra.html
  - id: handbrake
    resource: https://handbrake.fr/docs/en/latest/cli/command-line-reference.html
---
# Captura 1: A Better Finder Attributes

Configuración visible: `Advanced date manipulation`; usar `Date embedded in
the file name`; extraer fecha y hora con `YYYY-MM-DD hh.mm.ss`, meses numéricos
y reloj de 24 horas. Sobrescribir fechas de creación y modificación del archivo.
En imágenes: `Set DateTimeOriginal & DateTimeDigitized`; en películas:
`Use Apple Photos Brute Force Mode`. `Change: Keep unchanged` no introduce
un desplazamiento adicional. Procesar archivos y carpetas está marcado;
subcarpetas y su contenido está desmarcado.[^screenshots]

Propuesta: leer la fecha del nombre con un parser estricto; una política
`filename-to-metadata` escribiría `EXIF:DateTimeOriginal` y `EXIF:CreateDate`
(nombre usado por ExifTool para DateTimeDigitized), offsets cuando se conozcan,
y las fechas del sistema de archivos, como operaciones separadas y verificadas.
ExifTool sería el escritor principal; Pillow seguiría dedicado a imágenes.

Para MOV/MP4, especificar los grupos al escribir fechas QuickTime y conservar
la hora local con offset en `Keys:CreationDate`. Las fechas enteras QuickTime
deben representar UTC cuando se trate de un origen conforme; ExifTool documenta
que algunas cámaras guardan hora local en su lugar. No activar una conversión
universal sin conocer el origen. Un timestamp sin zona no permite inferir UTC
de manera fiable.[^quicktime]

En macOS `FileCreateDate` requiere el ejecutable `setfile` para escritura
según ExifTool; el preflight debe comprobar la capacidad real del entorno.
Cambiar EXIF y cambiar fechas del sistema de archivos son resultados distintos.
Si uno no está soportado, registrar la limitación y abrir una pausa manual.[^filesystem]

La captura no revela qué tags concretos escribe el modo Apple Photos Brute
Force. No se afirma equivalencia exacta. Un ensayo con copias de JPEG, MOV y
MP4 reales debe comparar tags antes/después y la fecha mostrada en Apple Photos.
Hasta entonces, los casos que necesiten esa compatibilidad conservan la salida
manual. No copiar indiscriminadamente todos los tags estructurales de un vídeo
original sobre otro recodificado.

# Captura 2: A Better Finder Rename

Categoría `Date & Time`, acción `Rename to date/time`, modo Simple. Fecha
`YYYY-MM-DD`, hora `HH.MM.SS (24 hour clock)`, formato `Date Time`; usa
`Content Creation Date (e.g. EXIF)`. Cambia solo el nombre sin extensión.
Procesa archivos y carpetas, sin recursión a subcarpetas.[^screenshots]

Propuesta: política inversa `metadata-to-filename` con fecha de captura
seleccionada explícitamente. En imágenes priorizar `DateTimeOriginal` y su
offset; `CreateDate` solo como fallback configurado. En vídeos, resolver
`Keys:CreationDate`/fechas QuickTime con su semántica de zona. Mostrar la fuente
elegida, mantener la extensión y ofrecer el nombre canónico
`YYYY-MM-DD HH.MM.SS.ext`. Conservar por defecto el texto descriptivo existente
es una mejora propuesta, configurable; reproducir la captura permite descartarlo.

Nunca aplicar ambas direcciones a un conflicto sin una decisión previa sobre
la fuente correcta. No usar automáticamente mtime como fecha de captura.
Resolver colisiones sin sobrescribir: proponer un sufijo estable ` (2)`,
` (3)`, etc., considerando también mayúsculas y normalización Unicode en macOS.
La normalización de extensiones es otra opción independiente.

# Captura 3: HandBrake

Fuente visible: MP4, 1080×1920, 29,8668 FPS, SDR de 8 bits, una pista de audio,
27 s. Preset `Fast 720p30`. Salida MP4 con `Passthru Common Metadata` y
`Align A/V Start` marcados; `Web Optimized` e iPod 5G desmarcados. Vídeo
H.264 (x264), `30 FPS PFR`; audio AAC (CoreAudio), estéreo. Filtros visibles:
Comb Detect y Decomb. Tamaño: **1080×720 Storage, 405×720 Display**.[^screenshots]

PFR limita a 30 FPS y conserva el timing de fuentes por debajo de ese límite;
CFR fuerza tasa constante. El tamaño de almacenamiento distinto del mostrado
indica píxel no cuadrado. No equivale a una salida vertical 720×1280. La captura
no muestra RF, bitrate de audio, pestaña Dimensions ni todos los ajustes del
preset. No se pueden recuperar exactamente desde ella.[^handbrake]

Propuesta predeterminada: MP4 H.264, hasta 30 FPS PFR para respetar la captura,
SAR 1:1, sin recorte ni ampliación, encajando el tamaño visual en 1280×720
si es apaisado y 720×1280 si es vertical. Ejemplos: 1920×1080 → 1280×720;
1080×1920 → 720×1280. Es una decisión propuesta para mantener más detalle.
Un perfil alternativo `height-720` reproduce aproximadamente los 405×720
visuales de la captura, redondeando dimensiones a valores admitidos por x264.
Ofrecer CFR 30 como opción explícita si se quieren exactamente 30 frames/s.

Usar HandBrakeCLI porque ya es una dependencia, exportar un preset JSON y
registrar su huella y la versión del codificador. La implementación ajustará
límites por orientación efectiva, rotación y DAR, sin reutilizar a ciegas el
ancho/alto de almacenamiento. FFmpeg sería una alternativa si una prueba
demuestra límites en ese control, no una segunda implementación inicial.

Mantener los metadatos comunes y alinear audio/vídeo, pero releer y verificar
las fechas seleccionadas después de comprimir. Preservar orientación visible,
audio y duración; una fuente HDR, varias pistas o subtítulos necesita una
política explícita antes de sustituirla. La comprobación automática de tamaño
no sustituye una revisión visual de calidad en la primera muestra.

[^screenshots]: Capturas aportadas por el usuario el 2026-11-13; transcripción visual, sin archivos de imagen incorporados al repositorio.
[^quicktime]: [Semántica QuickTime en ExifTool](https://github.com/exiftool/exiftool/blob/master/html/TagNames/QuickTime.html).
[^filesystem]: [Fechas del sistema de archivos en ExifTool](https://github.com/exiftool/exiftool/blob/master/html/TagNames/Extra.html).
[^handbrake]: [Referencia oficial de HandBrakeCLI](https://handbrake.fr/docs/en/latest/cli/command-line-reference.html).
