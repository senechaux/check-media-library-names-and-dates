## Why

El README exige alternar scripts y aplicaciones, recordar carpetas y repetir
auditorías a mano. Un proceso interactivo debe guiar ese recorrido y poder
reanudarlo sin perder decisiones ni asumir que una tarea manual ya se hizo.

## What Changes

- Añadir `python3 -m media_library run --config …` y modos de simulación/aplicación.
- Ejecutar etapas ordenadas sobre el contrato común, con resultados persistentes.
- Ofrecer pausas con instrucciones, confirmación y validación posterior.
- Reanudar tras Ctrl+C, cierre de terminal o fallo, con códigos de salida estables.
- Integrar adaptadores automáticos progresivamente, manteniendo alternativas manuales.

## Capabilities

### New Capabilities
- `guided-pipeline`: comando único, etapas, interacción, reanudación e informe final.

### Modified Capabilities
Ninguna; consume `safe-execution` sin cambiar sus garantías.

## Impact

Depende de `safe-execution-core`. Las etapas EXIF, compresión y exportación usan
adaptadores manuales hasta integrar sus cambios respectivos. No se llamará a
los `main()` mutadores históricos. No incluye automatización de interfaces GUI,
sincronización Dropbox/Drive ni una interfaz web. Un solo comando no implica
ausencia de intervención humana.
