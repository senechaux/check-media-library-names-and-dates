## 1. Derivados y validación
- [x] 1.1 Definir recetas y fuentes de mayor calidad, destinos por ruta/ID y descubrimiento de años.
- [x] 1.2 Implementar exportación JPG con orientación, límite 1200, fechas y política de color; tratar EXIF ausente.
- [x] 1.3 Reutilizar codificación para perfil upload-480p30 con geometría correcta y fechas verificadas.
- [x] 1.4 Implementar publicación validada, vigencia por receta/huellas y recuperación de parciales.

## 2. Auditoría y entrega
- [x] 2.1 Implementar auditoría de cobertura y distinguir exclusiones, errores y pendientes.
- [x] 2.2 Implementar modos disabled/manual y sus evidencias, instrucciones y pausas.
- [ ] 2.3 Evaluar versión/scopes/autenticación del uploader; implementar configured-cli solo si puede limitarse al alcance previsto.
- [x] 2.4 Implementar backup verificado del estado tras éxito y reanudación sin volver a subir.

## 3. Verificación e integración final
- [x] 3.1 Verificar escenarios verified-delivery con fuentes homónimas, sin EXIF, rotadas, perfiles cambiados y resultados parciales.
- [x] 3.2 Simular carga fallida, resultado remoto incierto, ausencia de recibos y fallo de backup sin cuentas ni tráfico remoto real.
- [x] 3.3 Verificar el recorrido completo del comando único en copias de muestra, incluidos todos los adaptadores reales, pausa y reanudación.
- [ ] 3.4 Documentar capacidades comprobadas y limitaciones API; mantener pendientes las pruebas de cuenta real hasta tener un lote de prueba autorizado.
