## 1. Contratos y configuración
- [ ] 1.1 Añadir paquete instalable, configuración TOML validada y ejemplo sin datos personales.
- [ ] 1.2 Definir StageResult, incidencias, operaciones y esquema versionado del manifiesto; documentar compatibilidad.
- [ ] 1.3 Implementar preflight de rutas resueltas, permisos, capacidades de herramientas y espacio.

## 2. Inventario y ejecución segura
- [ ] 2.1 Unificar recorrido, exclusiones y detección de formatos sin depender de nombres válidos.
- [ ] 2.2 Asignar IDs/destinos por entrada y corregir recuentos y volcado local.
- [ ] 2.3 Sustituir shell interpolado y errores ocultos por resultados estructurados comprobados.

## 3. Estado y operaciones
- [ ] 3.1 Implementar manifiesto atómico, journal y bloqueo por origen con recuperación explícita de bloqueos obsoletos.
- [ ] 3.2 Implementar huellas, backups verificados y precondiciones sin sobrescrituras.
- [ ] 3.3 Adaptar funciones reutilizables y conservar entradas antiguas sin invocar movimientos inseguros desde el nuevo flujo.

## 4. Verificación
- [ ] 4.1 Verificar todos los escenarios de safe-execution con archivos temporales, incluidos nombres especiales y mismo basename.
- [ ] 4.2 Inyectar fallos de disco/proceso/guardado y comprobar backup, bloqueo y recuperación.
- [ ] 4.3 Actualizar OKF y guía de instalación con capacidades realmente implementadas y resultados de comprobación.
