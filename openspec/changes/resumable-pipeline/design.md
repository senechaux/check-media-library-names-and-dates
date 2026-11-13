## Context

El [plan general](../../../docs/knowledge/automatizacion.md) define el recorrido.
La primera versión debe funcionar con acciones externas, de modo que reemplazar
un adaptador manual por otro automático no cambie el control del proceso.

## Decisions

1. `run --config <toml>` ejecuta preflight, checklist de importación/revisión,
   inventario, plan, nombres/fechas, normalización MP4, compresión, instalación,
   exportación, auditoría final, entrega y cierre. Etapas opcionales se registran
   como deshabilitadas; el informe declara el alcance efectivamente completado.
2. Sin flags, presentar operaciones y pedir aprobación del lote antes de mutar.
   `--dry-run` produce plan/informes/estado sin cambiar medios ni lanzar una
   carga; no espera tareas manuales. `--apply` autoriza las operaciones automáticas
   configuradas, pero no elige autoridad de fechas ni completa pausas humanas.
3. La pausa guarda ID, etapa, archivos, instrucciones, evidencia esperada,
   decisiones y condición de reanudación. El usuario puede comprobar de nuevo,
   posponer o cancelar. Una selección por archivo permite continuar con elementos
   independientes, pero un elemento pendiente no puede avanzar a sustitución/carga.
4. Para Attributes/Rename, preparar copias de trabajo por ID y un listado exacto
   de operaciones; la app actúa sobre esas copias, no sobre originales. Para
   HandBrake se conserva un mapa ID → entrada → salida esperada. Los renombrados
   externos necesitan asociación inequívoca por huella del contenido o decisión
   explícita: nunca adivinar entre dos archivos por nombre o posición.
5. En terminal, esperar usando entrada bloqueante. Confirmar solicita reauditar:
   EXIF/fechas, nombre esperado o compresión, según la etapa. Un resultado inválido
   conserva la pausa con diagnóstico. Cuando el estado no es comprobable localmente
   (p. ej. subida web), guardar confirmación humana y declararla como tal.
6. Sin TTY o con EOF, guardar `WAITING_USER` y salir con 2. `--resume <run-id>`
   carga su configuración congelada, recupera el bloqueo y comprueba estado y
   huellas. Cambiar configuración exige nuevo plan; no aplicar otro preset
   silenciosamente. Ctrl+C guarda la pausa/interrupción y sale con 130.
7. Completar con 0 solo cuando no haya errores ni operaciones pendientes en el
   alcance habilitado. Pendientes → 2; fallo operativo → 3. Incluir resumen por
   etapa, archivos cambiados, conservados, omitidos con razón, pendientes y fallos,
   rutas de informes y siguiente orden de reanudación.

## Risks / Trade-offs

No automatizar clics evita depender de versiones/idiomas de las apps. Para no
bloquear la primera entrega, los validadores se inyectan con el contrato de etapa;
la integración definitiva pertenece al cambio correspondiente. Una etapa sin
validador disponible informa de la limitación y no se considera validada.
El orquestador puede completarse con adaptadores simulados: no depende de que
se terminen los cambios que lo consumen. Cada cambio posterior integra su etapa;
la prueba completa con todos los servicios reales pertenece a la última entrega.

## Migration Plan

Documentar instalación única y tres recorridos: todo automático, una corrección
manual y reanudación sin terminal. Mantener los scripts antiguos disponibles,
pero enlazar el nuevo comando como entrada recomendada solo cuando el recorrido
completo tenga sus adaptadores y verificaciones.
