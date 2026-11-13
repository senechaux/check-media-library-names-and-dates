## ADDED Requirements

### Requirement: Fechas válidas y comparación por precisión
El sistema SHALL validar fechas con calendario, admitir timestamps ISO con Z/offset y con/sin fracción, y comparar a la precisión común. Fechas coincidentes SHALL considerarse correctas.

#### Scenario: Igualdad y distintas representaciones
- **WHEN** nombre y tags representan el mismo instante, con o sin fracción y tras aplicar su zona conocida
- **THEN** se clasifican como coincidentes y no se propone corregirlos.

#### Scenario: Diferencia arbitraria de dos horas y cincuenta y nueve minutos
- **WHEN** dos fechas difieren 2 h 59 min sin evidencia de zona que las haga equivalentes
- **THEN** se registra discrepancia, sin aceptarla como ajuste horario.

### Requirement: Autoridad temporal explícita
El sistema SHALL conservar fuentes y precisión y requerir una política explícita antes de elegir entre fechas discrepantes. SHALL NOT fabricar mes, día, hora o zona como si estuvieran acreditados.

#### Scenario: Nombre correcto y EXIF incorrecto según revisión
- **WHEN** el usuario elige filename-to-metadata para un archivo
- **THEN** el plan mantiene su nombre y propone las escrituras de fecha derivadas de él.

#### Scenario: Foto antigua con solo año
- **WHEN** la única evidencia es `1987 vacaciones.jpg`
- **THEN** se registra precisión de año y no se escribe automáticamente 1 de enero a medianoche.

### Requirement: Zonas horarias y DST sin inferencias silenciosas
El sistema SHALL distinguir horas locales e instantes con offset, registrar la zona configurada para fechas sin offset y solicitar decisión ante horas DST inexistentes o ambiguas.

#### Scenario: Hora repetida en Madrid
- **WHEN** el nombre contiene `2026-10-25 02.30.00` sin offset y se aplica Europe/Madrid
- **THEN** se pide decidir el offset antes de escribir fechas UTC.

#### Scenario: Hora inexistente en Madrid
- **WHEN** el nombre contiene `2026-03-29 02.30.00` sin offset y se aplica Europe/Madrid
- **THEN** se informa de una hora inexistente sin normalizarla silenciosamente.

### Requirement: Escritura de fechas verificable por formato
El sistema SHALL modificar solo los campos acordados, verificar cada campo objetivo y conservar el contenido del medio. Una capacidad no soportada SHALL generar incidencia o pausa manual.

#### Scenario: JPEG desde nombre
- **WHEN** se autoriza la fecha `2026-11-10 18.59.08` para un JPEG
- **THEN** DateTimeOriginal y DateTimeDigitized reflejan esa hora y las fechas del sistema solicitadas se verifican por separado.

#### Scenario: Escritura QuickTime y lectura posterior
- **WHEN** un MP4 se corrige con una hora local y offset seleccionados
- **THEN** los tags objetivo UTC y locales representan el mismo instante después de releerlos.

#### Scenario: Falta capacidad de escribir fecha de creación
- **WHEN** la plataforma no permite modificar FileCreateDate
- **THEN** la operación se declara incompleta y ofrece instrucciones manuales sin afirmar equivalencia total.

### Requirement: Renombrado desde metadatos sin pérdida ni sobrescritura
El sistema SHALL proponer nombres canónicos desde la fecha de captura seleccionada, mantener extensión y descripción por defecto y resolver conflictos antes de ejecutar.

#### Scenario: Dos fotos en el mismo segundo
- **WHEN** dos fotos del mismo álbum generan el mismo nombre canónico
- **THEN** se proponen destinos distintos con sufijos estables, conservando ambos archivos y su correspondencia.

#### Scenario: Cambio solo de mayúsculas o ciclo
- **WHEN** el plan requiere un renombrado de mayúsculas o intercambiar dos nombres
- **THEN** se completa con destinos temporales sin sobrescribir contenido y se puede recuperar una interrupción.

### Requirement: Auditoría repetible y etiquetas históricas
El sistema SHALL volver a auditar todos los archivos, incluidos los prefijados por versiones anteriores, sin añadir prefijos para expresar incidencias nuevas.

#### Scenario: Archivo marcado en una ejecución antigua
- **WHEN** existe `diff_datetime 2026-11-10 18.59.08.jpg`
- **THEN** se audita, se conserva su identidad y solo se propone quitar el prefijo tras resolver la incidencia.

#### Scenario: Segunda ejecución sobre archivos ya corregidos
- **WHEN** fechas y nombres ya cumplen la política elegida
- **THEN** no se proponen nuevas escrituras ni nuevos renombrados.
