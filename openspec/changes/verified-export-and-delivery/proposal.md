## Why

El exportador puede mover archivos parciales y omitir derivados inválidos porque
ya existen. La carga y su backup son órdenes manuales del README sin evidencia
integrada. El proceso completo necesita comprobar qué se exportó y qué se entregó.

## What Changes

- Crear derivados de imágenes de hasta 1200 px y vídeos con un perfil de carga separado.
- Reutilizar inventario, fechas, ejecución y validadores sin duplicar implementaciones.
- Verificar orientación, fechas, integridad y vigencia antes de omitir derivados.
- Añadir auditoría final e informe de cobertura local y entrega remota diferenciadas.
- Integrar carga manual o CLI expresamente configurada y respaldar su estado tras éxito.

## Capabilities

### New Capabilities
- `verified-delivery`: exportación fiable, validación final y entrega con evidencia.

### Modified Capabilities
Ninguna; integra las cuatro capacidades previas.

## Impact

Depende de `safe-execution-core`, `resumable-pipeline`, `metadata-and-naming` y
`validated-video-compression`. Sustituirá el lanzador con años fijos por recorrido
configurable. Fuera de alcance: borrar contenido remoto, gestionar toda la
biblioteca de Google Photos o implementar sincronización Dropbox/Drive.
El adaptador gphotos-uploader-cli queda condicionado a comprobar su versión,
autenticación y compatibilidad actuales; el modo manual permite cerrar el flujo.
