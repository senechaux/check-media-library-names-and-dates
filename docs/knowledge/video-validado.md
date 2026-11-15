---
type: Reference
title: Normalización y compresión de vídeo implementadas
description: Perfil reproducible, validación técnica, publicación recuperable y revisión visual pendiente.
tags: [actual, video, handbrake, ffmpeg, recuperacion]
status: draft
x_analysis_date: "2026-11-15"
sources:
  - id: planning
    resource: ../../src/media_library/video_plan.py
  - id: driver
    resource: ../../src/media_library/video_driver.py
  - id: pipeline
    resource: ../../src/media_library/video_stage.py
  - id: tests
    resource: ../../tests/test_video_recovery_integration.py
  - id: handbrake
    resource: https://handbrake.fr/docs/en/latest/cli/command-line-reference.html
---
# Qué funciona

`normalize` y `compression` usan servicios reales con ffprobe, HandBrakeCLI,
FFmpeg y ExifTool. `installation` publica mediante el [núcleo seguro](nucleo-seguro.md),
con original archivado y recuperación por journal. [Exportación y auditoría](exportacion-entrega.md)
ya usan servicios reales. La entrega optativa requiere declaración o un cliente
configurado con alcance; en pruebas su transporte es simulado. No se ha archivado
ningún cambio ni usado una cuenta real.

El plan registra tamaño, umbral, bitrate diagnóstico, contenedor real y marca,
acción, etapa responsable, destino, geometría, perfil y huella de opciones/preset.
ffprobe agrupa MOV/MP4: la marca `major_brand` distingue ambos, sin depender del
sufijo. La normalización de vídeos pequeños no depende del umbral de grandes.
Remux compatible y compresión se distinguen; cuando hace falta recodificar,
normalización y compresión se combinan en una sola codificación de vídeo.[^planning]

# Configuración y decisiones

La tabla opcional `[video]` se congela con el resto del TOML. Valores iniciales:

```toml
[video]
min_bytes = 50000000
profile = "archive-720p30" # Alternativa: height-720.
frame_rate_mode = "pfr"   # cfr solicita 30 FPS constantes.
quality = 22             # RF propuesto, pendiente de revisión visual humana.
encoder_preset = "fast"
audio_encoder = "ffmpeg_aac"
min_savings_bytes = 1
min_savings_ratio = 0.0
allow_remux_growth = false
historical_policy = "review" # keep | process, solo tras revisión explícita.
quality_reviewed = false
```

El tamaño selecciona con `>=`; bitrate no añade otro umbral. Una publicación
anterior con el mismo perfil solo se reutiliza si el manifiesto acredita la
operación completa y siguen íntegros resultado y backup. El texto `reduced_size`
o `reduced_video` sin evidencia exige `historical_policy`: `review` deja pausa,
`keep` conserva por decisión explícita y `process` permite un plan nuevo.
Los `_full_path.txt` heredados siguen siendo incidencias del inventario: no se
ejecutan sus rutas ni se limpian carpetas globales.

Para este alcance, habilitar normalize/compression/installation y las fechas
que correspondan; deshabilitar import_review, export, audit y delivery. Las
imágenes no reciben transformación de vídeo. `--dry-run` sondea y muestra el
plan sin codificar, crear candidatos ni modificar medios. Las instrucciones
de [fechas](fechas-nombres.md) explican cómo elegir autoridad/zona antes de actuar.
Si metadata está deshabilitada, vídeo sigue exigiendo una fecha explícitamente
resuelta por el mismo servicio común. No usa mtime como fallback.

Para preparar derivados sin sustituir originales, deshabilitar installation.
Con installation habilitada y `quality_reviewed=false`, el candidato puede pasar
validación técnica y queda en pausa antes de publicar. Después de revisar una
muestra representativa con los mismos ajustes:

```text
decidir quality_reviewed=true
comprobar
```

Es una declaración humana persistente; el programa no determina calidad visual.
Puede declararse en TOML para un lote cuyo perfil ya se haya revisado. Cambiar
calidad/perfil exige una planificación nueva. En la pausa de transformación se
pueden guardar `historical_policy=keep|process` o `allow_remux_growth=true`.
Una confirmación no sustituye al validador técnico.

# Geometría, timing y pistas

Se aplican SAR y matriz de rotación al calcular la geometría visual. El perfil
principal encaja en 1280×720 apaisado, 720×1280 vertical o 720×720 cuadrado;
`height-720` limita la altura a 720. Se redondea a dimensiones pares con error
relativo de DAR <=0,5%, sin ampliar, recortar ni añadir bordes. Si no hay una
solución acreditable, se conserva la pausa. HandBrake 1.11.2 aplica la matriz de
rotación al leer: no se añade otro giro. Se verifican geometría, SAR 1:1 y ausencia
de rotación residual en la salida. La prueba rotada contrasta orientación con
la referencia decodificada por FFmpeg; no es una revisión de calidad.

PFR limita a 30 FPS y conserva los timestamps por debajo del límite. CFR solicita
30 constantes, incluyendo duplicación cuando la fuente es de 24. La validación
inspecciona timestamps de todos los frames, además de las tasas declaradas.
No confunde un promedio <=30 con un límite entre frames.[^handbrake]

El perfil simple admite SDR progresivo con una pista de vídeo y cero o una de
audio mono/estéreo. HDR, profundidad de color no cubierta, varias pistas,
subtítulos, entrelazado o matrices reflejadas abren pausa antes de convertir.
No existe todavía política para eliminarlos, reducirlos o tone-mapping; el modo
manual tampoco permite saltarse esa comprobación. Comb Detect/Decomb están
desactivados para estas fuentes progresivas.

Se ha probado `audio_encoder="ffmpeg_aac"`: HandBrake codifica una vez el vídeo;
si hay audio, FFmpeg produce AAC estéreo a 160 kbit/s y lo multiplexa copiando el
vídeo, sin segunda recodificación de imagen. Registra ambos comandos y verifica
pistas/duraciones. `ca_aac` y `av_aac` son opciones explícitas de HandBrake que
requieren soporte en su build. En este host `ca_aac` anunció soporte pero falló
al inicializar AudioConverter; no se declara compatible. El audio sintetizado
sí pasó por la ruta FFmpeg AAC. Sin audio no se inventa una pista silenciosa.

# Validación y publicación

El preset JSON y su huella, las versiones y comandos exactos quedan conservados
por ejecución/ID. Se requiere salida MP4/H.264 real, decodificación completa con
FFmpeg y código de proceso correcto. La duración puede diferir como máximo
`max(0,1 s, dos frames de salida)`. Se comprueban tamaño/geometría, SAR, orientación,
FPS/timestamps, pistas/audio y fechas restauradas y releídas con ExifTool. Las
fechas del filesystem solicitadas se reaplican y verifican en el destino final.
No se copian indiscriminadamente tags estructurales del original recodificado.[^driver]

La compresión exige salida positiva y menor, además de ambos mínimos de ahorro.
Si no los alcanza, registra `not_beneficial`, conserva el original y el candidato
para revisión, y no vuelve a codificar al reanudar ni ajusta RF en bucle. Ese
resultado completa el intento conservando el archivo, sin afirmar que se normalizó.
Un remux que crece necesita autorización separada; sus paquetes deben conservarse.

La operación `substitute` publica en `nombre reduced_size.mp4` al recodificar,
o `nombre.mp4` al remultiplexar. Conserva jerarquía e ID, verifica el archivo
íntegro del original y publica un enlace exclusivo desde un temporal local del
volumen del álbum. Solo después retira el original cuya huella aún coincida.
Una colisión bloquea ese archivo y conserva sus temporales; los independientes
pueden terminar. Tampoco adopta un destino en colisión porque tenga bytes iguales.

Cada paso es duradero en el journal; al reanudar se acreditan candidatos,
publicaciones y backups sin recodificar resultados completos. La limpieza exige
`COMPLETED` y vuelve a verificar salida/backup. Retira únicamente candidatos,
intermedios y copias manuales propios cuyos hashes aún coincidan. Conserva
presets, backups y pendientes; no borra carpetas completas. El candidato puede
desaparecer después de limpiar sin invalidar la publicación acreditada.[^pipeline]

# Requisitos y comprobaciones pendientes

Se requieren Python >=3.11, HandBrakeCLI, FFmpeg/ffprobe y ExifTool en PATH o
declarados en `[tools]`. Probados Python 3.12.15, HandBrakeCLI 1.11.2,
FFmpeg/ffprobe 9.0.2 y ExifTool 13.40. Configurar un timeout suficiente para cada
subproceso y espacio para candidato, intermedio de audio, archivo y publicación.
La versión de HandBrake debe admitir importación JSON y las opciones del perfil;
si falta herramienta/capacidad se conserva la pausa.

La tarea 3.4 permanece pendiente: con copias locales no personales, comparar
original/candidato en un reproductor
fiable, con la misma visualización, en muestras horizontales, verticales,
rotadas, oscuras y de movimiento/textura; revisar detalle, artefactos, fluidez y
sincronía A/V. Registrar perfil/RF, versiones, hashes y decisión humana antes de
aplicar al lote. Las pruebas sintéticas técnicas no acreditan esa calidad.
RF 22, AAC de FFmpeg y el vertical cuadrado difieren de ajustes no visibles o del
vertical anamórfico 405×720 de la captura; no se afirma equivalencia exacta.

La tarea 3.3 de metadata sigue pendiente y no se afirma equivalencia con Apple
Photos Brute Force. Exportación/entrega ya tiene implementación local y protocolo,
con adaptador/autenticación real de gphotos pendiente en su tarea 2.3.
Véase [verificación](verificacion.md) para resultados reproducibles.

[^planning]: [Planificador de vídeo](../../src/media_library/video_plan.py).
[^driver]: [Codificación y validación reales](../../src/media_library/video_driver.py).
[^pipeline]: [Adaptadores y limpieza por operación](../../src/media_library/video_stage.py).
[^handbrake]: [Referencia oficial de HandBrakeCLI](https://handbrake.fr/docs/en/latest/cli/command-line-reference.html).
