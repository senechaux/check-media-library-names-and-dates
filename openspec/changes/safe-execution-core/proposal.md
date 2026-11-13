## Why

Los scripts usan rutas relativas o personales, resultados poco estructurados y
temporales por basename. Automatizarlos así propagaría omisiones y colisiones.
Hace falta una base común que permita planificar, validar y recuperar operaciones.
Evidencia: [flujo actual](../../../docs/knowledge/flujo-actual.md) y fichas enlazadas.

## What Changes

- Crear un paquete Python instalable con configuración TOML y contratos de etapa.
- Inventariar medios sin exigir nombres válidos; unificar exclusiones y formatos.
- Introducir manifiesto versionado, bloqueo, huellas y resultados por operación.
- Preparar operaciones con backups, precondiciones y recuperación explícita.
- Convertir errores ocultos en resultados estructurados.

## Capabilities

### New Capabilities
- `safe-execution`: configuración, inventario, trazabilidad y operaciones verificables.

### Modified Capabilities
Ninguna especificación previa. Los scripts existentes siguen siendo entradas
compatibles durante la migración; su integración se hará por funciones seguras.

## Impact

Dependencias: ninguna. Desbloquea los otros cuatro cambios. Afectará a
`common_functions.py` y nuevo paquete/configuración/fixtures.
No incluir motores EXIF, codificación, sincronización remota ni limpieza global.
No ejecutar `move-biggest-videos.main()` como parte de un adaptador.
