## 1. Lectura y decisiones
- [x] 1.1 Implementar CaptureDate, parser de nombres/calendario y lectura EXIF/QuickTime con grupos y offsets.
- [x] 1.2 Implementar comparación por precisión, zona IANA y resolución explícita de DST/conflictos.
- [x] 1.3 Implementar decisiones por lote/archivo y tratamiento de fechas parciales y prefijos históricos.

## 2. Operaciones e integración
- [x] 2.1 Crear plan de renombrado que preserve extensión/descripción y reserve destinos sin colisiones.
- [x] 2.2 Implementar renombrado recuperable, incluidas mayúsculas y ciclos.
- [x] 2.3 Implementar escritura selectiva con ExifTool, capacidades por formato y verificación de campos/contenido.
- [x] 2.4 Integrar las dos direcciones y el modo manual con copias, pausas y StageResult.

## 3. Verificación
- [x] 3.1 Cubrir escenarios capture-dates-and-names y regresiones de igualdad, 2 h 59 min, formatos ISO y fechas inválidas.
- [x] 3.2 Comprobar offset, DST de invierno/verano, metadatos ausentes y errores por archivo sin abortar la auditoría completa.
- [ ] 3.3 Ensayar equivalencia con Attributes/Rename y Apple Photos en copias locales; conservar alternativa manual si no se demuestra.
- [x] 3.4 Verificar idempotencia y conservación de contenido/metadatos ajenos; actualizar OKF con resultados reales.
