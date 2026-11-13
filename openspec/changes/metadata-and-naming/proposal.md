## Why

El código actual marca discrepancias pero no corrige EXIF, pierde los archivos
marcados en auditorías posteriores y compara mal las fechas de vídeo. El usuario
necesita sustituir Attributes/Rename cuando sea posible y revisar qué fecha manda.

## What Changes

- Unificar lectura de fechas de nombres, EXIF, QuickTime y sistema de archivos.
- Comparar fechas usando offsets y zona configurada, sin la heurística de horas.
- Ofrecer filename-to-metadata, metadata-to-filename y revisión de conflictos.
- Escribir metadatos con ExifTool y verificar el resultado en copias de trabajo.
- Renombrar sin colisiones y migrar prefijos históricos mediante una decisión explícita.

## Capabilities

### New Capabilities
- `capture-dates-and-names`: resolución temporal, escritura y renombrado reversibles.

### Modified Capabilities
Ninguna; usa los contratos de ejecución y pausas ya propuestos.

## Impact

Depende de `safe-execution-core`; integración interactiva sobre `resumable-pipeline`.
Afectará a las auditorías de nombres/fechas y añade ExifTool como dependencia
para automatización, con modo manual si no está disponible o el formato no admite
escritura. Fuera de alcance: inventar fechas exactas de fotos antiguas, geolocalizar
viajes o garantizar el modo propietario Apple Photos sin un ensayo de compatibilidad.
