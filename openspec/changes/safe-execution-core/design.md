## Context

El sistema actual comprende seis archivos Python. Se propone
Python >=3.11 por `tomllib`, `argparse` para CLI y JSON para el manifiesto;
sin base de datos ni framework adicional en la primera entrega.

## Decisions

1. Añadir `pyproject.toml` y un paquete importable `media_library` con modelos,
   configuración, inventario, proceso externo y almacenamiento de estado.
   Extraer funciones reutilizables de los scripts, manteniendo wrappers de CLI.
2. Resolver rutas respecto al TOML, no al cwd. Validar origen/trabajo/archivo/
   exportación disjuntos tras resolver symlinks, permisos y espacio. No seguir
   symlinks a medios fuera del origen. No crear destinos ni lanzar herramientas
   con efectos antes de validar toda la configuración.
3. Un ID persistente identifica cada entrada del manifiesto, incluso tras
   renombrarla. Dos rutas distintas con iguales bytes tienen IDs distintos.
   Los temporales usan `<workspace>/<run-id>/<file-id>/`; el archivo conserva
   `<archive>/<run-id>/<ruta-relativa-original>`. Nunca usar solo el basename.
4. Inventariar archivos con nombre irregular, extensiones en mayúsculas y
   formatos no soportados. Identificar contenedor/codec con ffprobe cuando
   corresponda. Los no soportados se reportan; no se convierten por extensión.
5. Ejecutar herramientas con listas de argumentos, timeout configurable,
   códigos comprobados y errores tipados. Un fallo por archivo conserva el
   diagnóstico; no significa cero incidencias ni éxito total.
6. Persistir JSON mediante temporal, flush/fsync y replace local; usar un journal
   de operaciones y bloqueo por origen resuelto. El manifiesto contiene
   `schema_version`, `run_id`, configuración efectiva, versiones, estado,
   entradas y eventos. Cada entrada incluye ID, rutas, stat, SHA-256 antes de
   mutar, decisión temporal y operaciones. Versiones desconocidas se rechazan.
7. Registrar intención y precondiciones antes de escribir; después verificar y
   registrar evidencia. Crear backup íntegro antes de modificar medios; una
   exportación nueva no lo necesita. Verificar backup por hash. Reanudar compara
   huellas y estado de ambos lados; nunca reintenta a ciegas ni sobrescribe.
8. Admitir distintas profundidades en el inventario sin presuponer una estructura
   fija de año y álbum.

Contrato de etapa: contexto de ejecución y entradas → `StageResult` con estado,
operaciones propuestas, incidencias y evidencia. El esquema del manifiesto y
este contrato se fijan antes de repartir implementaciones entre agentes.

## Risks / Trade-offs

Hashear una biblioteca completa es costoso: inventario inicial usa stat y la
huella se calcula al necesitar precondiciones o recuperación. El espacio
estimado es conservador; se vuelve a comprobar antes de escribir archivos grandes.
Un backup en el mismo disco permite deshacer operaciones, pero el backup externo
sigue siendo una fase explícita. No se promete atomicidad entre volúmenes.

## Migration Plan

Crear un ejemplo de configuración sin rutas personales y excluir configuración
local/estado del control de versiones. Mantener logs legibles como vista del
manifiesto. No importar automáticamente los `_full_path.txt` históricos: ofrecer
inventario de pendientes y revisión antes de asociarlos a una ejecución nueva.
