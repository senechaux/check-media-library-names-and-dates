## Context

Mantener dos objetivos: biblioteca local revisada con compresión 720p opcional,
y derivados para subir (1200 px / perfil 480p heredado como propuesta inicial).
No interpretar un volcado del árbol local como evidencia de carga remota.

## Decisions

1. Exportar a raíz disjunta conservando rutas relativas e identidad. Descubrir
   años/álbumes desde configuración/inventario, sin array 2000–2023. Cada receta
   identifica fuente de mayor calidad registrada, huella, decisión de fecha,
   perfil y versión. Usar original archivado cuando permita evitar volver a
   comprimir un derivado 720p; aplicar la decisión temporal común al resultado.
2. JPG inicial: aplicar orientación visual con ImageOps.exif_transpose, reducir
   lado mayor a 1200 sin ampliar, normalizar Orientation y actualizar dimensiones
   EXIF. Conservar fechas seleccionadas e ICC conforme a la conversión de color.
   Aceptar fotos sin bloque EXIF sin provocar KeyError, aunque la fecha de captura
   desconocida debe quedar reportada/resuelta antes de una entrega que la requiera.
   Formatos/modos no soportados se reportan, sin una conversión implícita destructiva.
3. Vídeo: reutilizar servicio de codificación/validación. Perfil `upload-480p30`
   propuesto con límites visuales 854×480 apaisado / 480×854 vertical, PFR <=30,
   sin ampliar/recortar y SAR 1:1. Conservar posibilidad de configurar otros perfiles;
   no pasar dimensiones originales para contradecir el límite. Saltar recodificación
   si una copia validada ya cumple exactamente la receta deseada.
4. Generar por ID a temporal, verificar legibilidad/decodificación, dimensiones,
   orientación y fechas y publicar sin sobrescrituras. Un archivo existente solo
   se reutiliza si coinciden receta/huellas y vuelve a pasar su validador. Un
   destino ajeno al manifiesto abre conflicto; un derivado propio inválido se
   conserva/aparta hasta publicar su sustituto verificado.
5. Auditoría final compara archivos elegibles y exportados con razones para cada
   exclusión. Medios corruptos, fecha requerida sin resolver o faltantes impiden
   iniciar la entrega de ese alcance. No usar prefijos para señalar problemas.
   Declarar el tipo de evidencia de cada etapa y mostrar pendientes antes de subir.
6. `upload=manual` como propuesta inicial; `disabled` completa solo alcance local.
   `configured-cli` requiere opt-in, ejecutable/argumentos explícitos, preflight
   de autenticación y un ensayo pequeño autorizado. Un returncode cero confirma
   que terminó el comando, no demuestra por sí solo presencia remota de cada medio.
   Guardar IDs/recibos por archivo si el adaptador los ofrece; en otro caso
   declarar esa limitación y pedir confirmación humana de la entrega.
   Si una interrupción deja incierto el resultado remoto, no repetir la carga
   automáticamente: reconciliar recibos/estado del cliente o pedir revisión.
7. El uploader usa solo la exportación aprobada, nunca el archivo de originales.
   Tras éxito, copiar el estado necesario a destino configurado, comprobar la copia
   y registrar recibo local sin exponer tokens en logs/Git. Si la carga termina y
   el backup falla, reanudar solo el backup, sin repetir la carga. Un CLI que no
   permita limitar el alcance se mantiene como tarea manual hasta configurarlo.

## Risks / Trade-offs

Google Photos cambió scopes y visibilidad de la Library API desde marzo de 2025:
no se debe prometer auditoría de toda la biblioteca con permisos de una app.
Las cargas siguen siendo posibles con appendonly; hay que comprobar el uploader
concreto. [Fuente oficial](https://developers.google.com/photos/support/updates).
No se ha probado ninguna cuenta ni se ha subido contenido durante la planificación.

## Migration Plan

Primero exportación local fiable; después verificación final del comando único;
por último adaptador opcional de carga. Mantener modo manual con evidencia
declarada. No instalar globalmente un uploader ni cambiar credenciales durante
la implementación sin que sea necesario para una prueba expresamente autorizada.
