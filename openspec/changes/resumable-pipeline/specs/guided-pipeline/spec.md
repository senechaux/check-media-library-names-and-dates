## ADDED Requirements

### Requirement: Entrada única y etapas explícitas
El sistema SHALL permitir ejecutar el alcance configurado con `python3 -m media_library run --config <archivo>` desde cualquier carpeta y mostrar las etapas habilitadas y sus resultados.

#### Scenario: Recorrido con etapas opcionales
- **WHEN** la carga remota está deshabilitada y las etapas locales finalizan
- **THEN** la ejecución informa éxito local y declara que no se realizó carga remota.

### Requirement: Simulación y autorización del plan
El sistema SHALL mostrar las operaciones antes de escribir y requerir aprobación interactiva o `--apply`. `--dry-run` SHALL limitarse a inventario, plan, estado e informes.

#### Scenario: Simulación con trabajo manual pendiente
- **WHEN** se usa `--dry-run` y faltan fechas o comprimidos
- **THEN** se informa del trabajo previsto sin esperar, renombrar, escribir metadatos, comprimir ni subir medios.

#### Scenario: Aplicación con conflicto sin resolver
- **WHEN** `--apply` encuentra un conflicto cuya autoridad temporal no se ha decidido
- **THEN** conserva la incidencia pendiente y no elige una fecha automáticamente.

### Requirement: Pausas humanas accionables
El sistema SHALL mostrar en cada pausa los archivos afectados, rutas, herramienta, ajustes y condición de finalización, y SHALL esperar una decisión explícita sin sondeo continuo.

#### Scenario: Compresión manual
- **WHEN** la compresión se configura como manual
- **THEN** se muestran entradas/salidas por ID y perfil requerido, y el proceso espera hasta comprobar, posponer o cancelar.

### Requirement: Confirmación seguida de validación
El sistema SHALL validar el resultado de una tarea externa después de confirmarla. Las tareas sin evidencia técnica disponible SHALL identificarse como confirmadas por el usuario, no verificadas automáticamente.

#### Scenario: Confirmación sin corregir EXIF
- **WHEN** se confirma una corrección pero persiste la discrepancia
- **THEN** se mantiene la pausa, se explica el fallo y el archivo no avanza.

#### Scenario: Confirmación de subida en navegador
- **WHEN** el usuario declara completada una carga web sin comprobante API
- **THEN** se registra esa declaración y el informe distingue su alcance de una verificación remota.

### Requirement: Reanudación persistente
El sistema SHALL conservar decisiones y operaciones verificadas entre ejecuciones. `--resume` SHALL recuperar el trabajo pendiente y comprobar cambios externos antes de continuar.

#### Scenario: Reanudar después de una corrección externa
- **WHEN** se reabre una ejecución pausada y sus copias de trabajo han sido corregidas
- **THEN** se validan los cambios esperados y se continúa sin repetir operaciones acreditadas.

#### Scenario: Cambio imprevisto del original
- **WHEN** al reanudar ha cambiado un original fuera de las operaciones previstas
- **THEN** se exige nuevo plan para ese archivo y se conserva el resto de evidencias.

### Requirement: Terminal ausente e interrupción
El sistema SHALL guardar el estado antes de salir por EOF, ausencia de terminal o interrupción. EOF SHALL NOT interpretarse como confirmación.

#### Scenario: Ejecución sin TTY necesita intervención
- **WHEN** una etapa manual no puede solicitar entrada
- **THEN** persiste WAITING_USER, sale con 2 e indica cómo reanudar.

#### Scenario: Ctrl+C durante la espera
- **WHEN** el usuario interrumpe una pausa
- **THEN** guarda los pendientes, libera el bloqueo y sale con 130.

### Requirement: Informe y códigos de salida fiables
El sistema SHALL usar 0 para completar el alcance, 2 para pendientes, 3 para fallos operativos y 130 para interrupción, con un informe de estados y motivos por archivo.

#### Scenario: Fallo parcial de un lote
- **WHEN** varios archivos terminan y uno falla operativamente
- **THEN** se conservan los éxitos acreditados y la ejecución sale con 3 sin afirmar éxito total.
