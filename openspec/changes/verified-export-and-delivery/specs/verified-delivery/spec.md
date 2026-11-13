## ADDED Requirements

### Requirement: Exportación por receta e identidad
El sistema SHALL generar derivados en una raíz independiente, conservando jerarquía y correspondencia, y registrar fuente, huella, decisión temporal, perfil y versión usados.

#### Scenario: Exportar dos álbumes homónimos
- **WHEN** hay dos archivos con igual basename en álbumes diferentes
- **THEN** ambos derivados tienen destinos y temporales independientes y conservan su relación con el origen.

#### Scenario: Fuente de mayor calidad conservada
- **WHEN** existe un original archivado válido y un derivado 720p del mismo vídeo
- **THEN** la receta de carga puede usar el original y aplica las fechas seleccionadas sin una segunda pérdida desde el derivado.

### Requirement: Imágenes pequeñas con orientación y fechas correctas
El sistema SHALL crear los JPG habilitados con lado mayor <=1200 px, sin ampliar, conservando orientación visual, fecha seleccionada y tratamiento de color declarado. La ausencia de EXIF SHALL NOT provocar un fallo no controlado.

#### Scenario: JPEG vertical orientado por EXIF
- **WHEN** un JPG necesita rotación indicada por EXIF
- **THEN** el derivado se ve correctamente, no supera 1200 px y su Orientation no provoca una segunda rotación.

#### Scenario: Imagen sin EXIF
- **WHEN** una imagen legible no tiene bloque EXIF
- **THEN** se exporta sin KeyError y su fecha se obtiene de una decisión válida o queda pendiente explícita.

### Requirement: Perfil de vídeo de carga independiente
El sistema SHALL aplicar el perfil de carga configurado con geometría según orientación y fechas verificadas. Los límites del perfil SHALL prevalecer sobre las dimensiones originales.

#### Scenario: Vídeo vertical con upload-480p30
- **WHEN** se exporta una fuente vertical 1080×1920
- **THEN** su salida cabe en 480×854, conserva proporción y orientación y no supera 30 FPS PFR.

### Requirement: Reutilización solo tras comprobar vigencia
El sistema SHALL omitir regeneración solo cuando coincidan receta/huellas y el derivado supere su validación. Una salida parcial o ajena SHALL NOT considerarse completada por existir.

#### Scenario: Destino parcial de una ejecución anterior
- **WHEN** existe un vídeo no decodificable en la ruta de exportación
- **THEN** se detecta el fallo, no se entrega y se recupera sin sobrescribir contenido ajeno.

#### Scenario: Cambio de perfil o de fecha seleccionada
- **WHEN** cambia la receta respecto a la del derivado guardado
- **THEN** el derivado se considera desactualizado y se propone regenerarlo.

### Requirement: Auditoría final con cobertura explícita
El sistema SHALL justificar exportados, omitidos y pendientes por archivo y bloquear la entrega del alcance si faltan derivados requeridos o quedan resultados inválidos.

#### Scenario: Archivo elegible omitido por error
- **WHEN** falta un derivado que exige el plan
- **THEN** el informe lo señala y no inicia una entrega que se presente como completa.

### Requirement: Entrega remota optativa con evidencia diferenciada
El sistema SHALL permitir entrega deshabilitada, manual o por CLI configurada explícitamente y SHALL distinguir validación local, salida del comando, comprobante remoto y confirmación humana.

#### Scenario: El comando de carga termina con cero
- **WHEN** el uploader no proporciona recibos verificables por archivo
- **THEN** se registra éxito del comando sin afirmar presencia remota individual y se solicita confirmación si el alcance exige entrega.

#### Scenario: Carga deshabilitada
- **WHEN** el usuario configura solo preparación local
- **THEN** no se ejecuta ningún cliente remoto y el informe declara el alcance local.

### Requirement: Backup recuperable del estado de entrega
El sistema SHALL respaldar y verificar el estado del uploader tras una entrega exitosa cuando esté habilitado, sin incluir credenciales en informes o control de versiones.

#### Scenario: Falla el backup después de subir
- **WHEN** la entrega queda acreditada pero falla su backup de estado
- **THEN** la ejecución no se declara completa y al reanudar se reintenta el backup sin repetir la carga acreditada.
