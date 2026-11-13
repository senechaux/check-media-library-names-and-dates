## Context

La transcripción de las dos apps y sus límites está en
[ajustes externos](../../../docs/knowledge/herramientas-externas.md). El nombre
puede ser la fuente correcta o estar equivocado: no hay una autoridad universal.

## Decisions

1. Modelar `CaptureDate` con valor original, fuente/tag, precisión (año, mes, día,
   segundo o fracción), offset/zona si existen y estado de confianza/decisión.
   Parsear calendarios reales, ISO 8601 con Z/offset y con/sin fracción. El nombre
   canónico tiene precisión de segundos: comparar en esa precisión, conservando
   fracciones existentes. No añadir Z a una hora local por conveniencia.
2. Prioridad de lectura propuesta en imágenes: DateTimeOriginal con offset;
   CreateDate con offset solo si se habilita ese fallback. En vídeos considerar
   Keys:CreationDate con offset y CreateDate/fechas de pista con semántica conocida.
   Si varias fuentes válidas discrepan, abrir conflicto incluso si existe prioridad.
   Nunca escoger silenciosamente mtime ni deducir zona por diferencias de 1/2 h.
3. Para timestamps sin offset, aplicar zona IANA configurada y registrar la
   suposición por archivo/lote. Hora inexistente por DST → revisión; hora repetida
   → elegir explícitamente offset/fold. La ubicación del ordenador no prueba la
   ubicación de captura. Admitir excepciones de zona por lote/archivo.
4. `review` es la política inicial. `filename-to-metadata` y `metadata-to-filename`
   requieren una selección explícita persistente para el lote/archivo. Con ambos
   valores válidos y distintos, mostrar antes/después y qué se conservará. Sin
   fecha completa, mantener la precisión y solicitar una decisión; no introducir
   enero/día 1/medianoche como si fueran datos conocidos.
5. ExifTool leerá JSON con grupos. Escribir solo tags de fecha acordados por formato:
   JPEG DateTimeOriginal/CreateDate y offsets correspondientes; QuickTime con
   grupos y UTC/local explícitos. Registrar capacidades por tipo, sin prometer
   escritura universal en PNG/GIF/HEIC. Restaurar también FileModifyDate y
   FileCreateDate si son operaciones solicitadas y soportadas en macOS.
6. Trabajar sobre copia íntegra con backup verificado y releer todos los campos
   objetivo, además de comprobar que el medio sigue siendo legible. No considerar
   escritura parcial como éxito. Otros metadatos y contenido visual se conservan;
   verificar con fixtures que no se altera la imagen/stream codificado cuando
   solo se tocan fechas. No aplicar indiscriminadamente `AllDates` o `All:All`.
7. Renombrar a `YYYY-MM-DD HH.MM.SS[ descripción].ext`, manteniendo extensión
   por defecto y descripción salvo opción explícita de descartarla para replicar
   la captura. Resolver colisiones proponiendo ` (2)`, ` (3)` en orden estable
   por ruta original; reservar todos los destinos antes de ejecutar. Resolver
   ciclos y renombrados solo de mayúsculas con temporales por ID sin sobrescribir.
8. Reconocer `diff_datetime ` y `exif_getting_error ` como etiquetas históricas
   dentro del inventario. No añadir nuevos prefijos: las incidencias viven en el
   manifiesto. Proponer retirarlos solo tras resolver la incidencia y validar el
   destino; no eliminarlos de forma general o mediante reemplazo en toda la ruta.

## Risks / Trade-offs

No se conoce el conjunto de tags del modo Apple Photos Brute Force. Hacer un
ensayo independiente sobre copias reales antes de declarar equivalencia; si
falla, mantener una pausa con instrucciones. Esos fixtures no deben contener
fotos personales en Git. Cadenas locales QuickTime de cámaras antiguas necesitan
política de origen; `QuickTimeUTC` no corrige automáticamente sus ambigüedades.

## Migration Plan

Primero lector y comparación, luego decisiones y nombres, después escritura.
Mantener auditoría de solo lectura y ofrecer informe JSON/legible en lugar de
marcar nombres. No activar cambios masivos sobre una biblioteca existente sin
revisar el primer plan y probar una muestra de formatos y años.
