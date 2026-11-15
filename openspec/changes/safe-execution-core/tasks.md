## 1. Contratos y configuración
- [x] 1.1 Añadir paquete instalable, configuración TOML validada y ejemplo sin datos personales.
- [x] 1.2 Definir StageResult, incidencias, operaciones y esquema versionado del manifiesto; documentar compatibilidad.
- [x] 1.3 Implementar preflight de rutas resueltas, permisos, capacidades de herramientas y espacio.

## 2. Inventario y ejecución segura
- [x] 2.1 Unificar recorrido, exclusiones y detección de formatos sin depender de nombres válidos.
- [x] 2.2 Asignar IDs y destinos independientes por entrada del inventario.
- [x] 2.3 Sustituir shell interpolado y errores ocultos por resultados estructurados comprobados.

## 3. Estado y operaciones
- [x] 3.1 Implementar manifiesto atómico, journal y bloqueo por origen con recuperación explícita de bloqueos obsoletos.
- [x] 3.2 Implementar huellas, backups verificados y precondiciones sin sobrescrituras.
- [x] 3.3 Adaptar funciones reutilizables y conservar entradas antiguas sin invocar movimientos inseguros desde el nuevo flujo.

## 4. Verificación
- [x] 4.0 Configurar pytest como dependencia de desarrollo, suite rápida e integraciones separadas según docs/knowledge/politica-tests.md; documentar sus comandos.
- [x] 4.1 Verificar todos los escenarios de safe-execution con archivos temporales, incluidos nombres especiales y mismo basename.
- [x] 4.2 Inyectar fallos de disco/proceso/guardado y comprobar backup, bloqueo y recuperación.
- [x] 4.3 Actualizar OKF y guía de instalación con capacidades realmente implementadas y resultados de comprobación.
- [x] 4.4 Corregir bloqueo por identidad efectiva del directorio, rechazar cambios de origen y verificar alias de mayúsculas/Unicode y directorios independientes.
- [x] 4.5 Acreditar propiedad de publicación por identidad del temporal, conservar rechazos de rename y verificar colisiones idénticas e interrupciones antes/después de publicar y limpiar el enlace local.
