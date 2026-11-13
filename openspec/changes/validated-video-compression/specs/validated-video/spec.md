## ADDED Requirements

### Requirement: Selección trazable y perfiles reproducibles
El sistema SHALL registrar por qué selecciona cada vídeo y el perfil, opciones y versión empleados. El umbral inicial SHALL ser 50.000.000 bytes y SHALL ser configurable.

#### Scenario: Límite y vídeo ya procesado
- **WHEN** un vídeo nuevo mide exactamente 50.000.000 bytes y otro ya tiene una salida validada con el mismo perfil
- **THEN** se selecciona el primero y se reutiliza la evidencia del segundo sin recodificarlo.

### Requirement: Resolución visual y orientación conservadas
El perfil archive-720p30 SHALL producir píxeles cuadrados, conservar orientación y proporción visual, sin recorte ni ampliación, con límites 1280×720 apaisado, 720×1280 vertical y 720×720 cuadrado.

#### Scenario: Vídeo vertical
- **WHEN** la fuente visual mide 1080×1920 y no tiene recortes
- **THEN** la salida propuesta mide 720×1280 con SAR 1:1 y se ve vertical sin deformación.

#### Scenario: Rotación y fuente pequeña
- **WHEN** una fuente 1920×1080 lleva rotación de 90 grados y otra fuente ya es 640×360
- **THEN** la primera se trata como vertical y la segunda no se amplía.

### Requirement: Política explícita de frame rate
El sistema SHALL usar hasta 30 FPS PFR por defecto y ofrecer CFR 30 como política distinta, registrando cuál se solicita y verificándola en la salida.

#### Scenario: Fuente de 24 FPS y fuente de 60 FPS
- **WHEN** se aplica el perfil PFR a ambas fuentes
- **THEN** la primera conserva su timing de 24 FPS y la segunda no supera 30 FPS.

### Requirement: Normalización real de contenedor
El sistema SHALL detectar formatos no MP4 y proponer remux o recodificación según compatibilidad, incluso por debajo del umbral de compresión. SHALL NOT simular una conversión cambiando la extensión.

#### Scenario: MOV compatible y compresión requerida
- **WHEN** una fuente MOV requiere además reducir resolución
- **THEN** se planifica una única recodificación a MP4, con asociación inequívoca al original MOV.

### Requirement: Validación completa antes de publicar
El sistema SHALL exigir proceso correcto, salida decodificable, duración y geometría dentro de las tolerancias acordadas, fechas verificadas y política de pistas respetada antes de publicar un resultado.

#### Scenario: Salida menor pero corrupta
- **WHEN** un archivo comprimido pesa menos pero no se decodifica completamente
- **THEN** no se publica ni se retira su original.

#### Scenario: Contenido con política no resuelta
- **WHEN** una fuente HDR o con varias pistas no tiene política de conservación aprobada
- **THEN** queda pendiente antes de cualquier conversión con pérdida de información.

### Requirement: Ahorro obligatorio para sustitución por compresión
El sistema SHALL mantener el original si el comprimido validado no es menor y SHALL separar ese resultado de un remux autorizado por normalización.

#### Scenario: Resultado mayor
- **WHEN** el comprimido pesa igual o más que la entrada
- **THEN** se registra not_beneficial y el original permanece en su álbum.

### Requirement: Sustitución recuperable y limpieza por operación
El sistema SHALL conservar un original verificado y publicar el resultado válido antes de retirar el original del álbum. Solo SHALL limpiar temporales de operaciones completadas, sin sobrescribir archivos existentes.

#### Scenario: Fallo al publicar después de copiar el backup
- **WHEN** falla la publicación en el álbum
- **THEN** el original sigue disponible en el álbum y el backup se conserva para recuperación.

#### Scenario: Interrupción tras publicar y antes de retirar original
- **WHEN** se reanuda con original y derivado validado presentes
- **THEN** se reconoce la publicación y se completa la operación sin volver a codificar ni duplicar el archivo.

#### Scenario: Dos resultados y una compresión aún pendiente
- **WHEN** se completan dos vídeos y un tercero sigue sin salida válida
- **THEN** solo se limpian los temporales de los dos completados y se mantiene la correspondencia del tercero.
