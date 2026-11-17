## Why

La selección actual copia vídeos grandes pero no los comprime. La sustitución
posterior carece de validación y puede limpiar entradas aún pendientes. El usuario
quiere automatizar HandBrake manteniendo orientación, fechas y originales recuperables.

## What Changes

- Seleccionar por tamaño configurable (50.000.000 bytes iniciales) y perfil.
- Añadir un perfil reproducible MP4/H.264, 720p según orientación, hasta 30 FPS PFR.
- Detectar contenedores reales y planificar normalización no MP4 sin duplicar recodificaciones.
- Validar salida, fechas y ahorro antes de publicar o retirar originales del álbum.
- Conservar archivo de originales e identidad por fichero; limpiar solo operaciones completas.

## Capabilities

### New Capabilities
- `validated-video`: compresión, normalización, validación y publicación de vídeos.

### Modified Capabilities
Ninguna; consume ejecución segura, fechas y etapas guiadas.

## Impact

Depende de `safe-execution-core`, `metadata-and-naming` y, para integración,
`resumable-pipeline`. Sustituirá la transferencia mediante `_full_path.txt` y
la secuencia insegura de `move-biggest-videos.py`. Mantiene HandBrakeCLI como
codificador y ffprobe/FFmpeg para inspección/validación; ExifTool para fechas.
Fuera de alcance: borrado del archivo de originales, réplicas remotas y
conversiones HDR o pérdida de pistas sin política explícita.
