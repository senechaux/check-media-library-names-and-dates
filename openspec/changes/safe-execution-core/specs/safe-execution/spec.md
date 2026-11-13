## ADDED Requirements

### Requirement: Configuración completa antes de modificar medios
El sistema SHALL validar rutas, permisos, exclusiones, herramientas necesarias y espacio antes de modificar medios. Las rutas relativas SHALL resolverse respecto al archivo de configuración.

#### Scenario: Ejecución desde otra carpeta
- **WHEN** se usa el mismo TOML desde dos directorios de trabajo distintos
- **THEN** el origen y todos los destinos resueltos son iguales.

#### Scenario: Destino solapado por enlace simbólico
- **WHEN** trabajo, archivo o exportación resuelve dentro del origen o se solapan entre sí
- **THEN** se rechaza la configuración sin modificar medios.

### Requirement: Inventario completo y consistente
El sistema SHALL inventariar medios independientemente del formato del nombre, aplicar exclusiones compartidas y reportar archivos no soportados o ilegibles como incidencias explícitas.

#### Scenario: Nombres y extensiones irregulares
- **WHEN** hay `IMG_0001.JPG`, un MOV y un archivo ilegible
- **THEN** aparecen tres entradas con su clasificación o error, sin omisiones silenciosas.

#### Scenario: Recuento local independiente del formato
- **WHEN** un álbum tiene tres PNG y un AVI, sin JPG ni MP4
- **THEN** se cuentan cuatro medios, los porcentajes usan el total de su categoría y el álbum cuenta cuatro archivos.

### Requirement: Identidad y destinos sin colisiones
El sistema SHALL conservar identidad y ruta original por archivo y asignar destinos sin colisiones, incluyendo equivalencias de mayúsculas y Unicode del volumen de destino.

#### Scenario: Dos álbumes con el mismo nombre de vídeo
- **WHEN** `a/2026-01-01 00.00.00.mp4` y `b/2026-01-01 00.00.00.mp4` se procesan
- **THEN** sus temporales, archivos conservados y operaciones quedan separados.

### Requirement: Proceso externo con resultado verificable
El sistema SHALL ejecutar herramientas sin shell interpolado y capturar código de salida, timeout y diagnóstico. Un error SHALL impedir marcar su operación como completada.

#### Scenario: Ruta con caracteres especiales
- **WHEN** un archivo contiene espacios, apóstrofos, comillas o `$()` en su nombre
- **THEN** la herramienta recibe literalmente esa ruta y no se ejecutan comandos adicionales.

#### Scenario: Proceso no cero con archivo parcial
- **WHEN** una herramienta devuelve estado no cero y deja una salida
- **THEN** la operación falla y la salida queda sin publicar.

### Requirement: Estado persistente y bloqueo
El sistema SHALL guardar un manifiesto versionado de forma atómica, registrar intención antes de mutar y evitar dos escritores sobre el mismo origen.

#### Scenario: Segunda ejecución concurrente
- **WHEN** otra ejecución mantiene el bloqueo del mismo origen resuelto
- **THEN** la nueva ejecución no modifica medios ni el manifiesto activo.

#### Scenario: Interrupción al persistir
- **WHEN** se interrumpe la escritura del estado
- **THEN** queda una versión anterior válida o una nueva completa y la recuperación identifica operaciones sin confirmar.

### Requirement: Backup y precondiciones antes de modificar
El sistema SHALL conservar un backup íntegro verificable antes de modificar un medio y volver a comprobar la huella de entrada. Un destino existente SHALL validarse o tratarse como conflicto, sin sobrescribirlo.

#### Scenario: Cambio externo después del plan
- **WHEN** la huella del origen ya no coincide con la prevista
- **THEN** se detiene esa operación y se solicita replantearla sin tocar el nuevo contenido.

#### Scenario: Recuperar una escritura incompleta
- **WHEN** una interrupción deja una operación sin confirmación y existe backup verificado
- **THEN** la recuperación compara los archivos presentes y ofrece restaurar o continuar sin repetir una mutación ya acreditada.
