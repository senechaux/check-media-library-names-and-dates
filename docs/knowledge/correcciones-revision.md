---
type: Reference
title: Correcciones de la revisión integral
description: Reproducciones, regresiones y límites de los seis fallos de seguridad revisados.
tags: [actual, verificacion, seguridad, recuperacion]
status: draft
sources:
  - id: tests
    resource: ../../tests/
  - id: core
    resource: nucleo-seguro.md
  - id: delivery
    resource: exportacion-entrega.md
  - id: video
    resource: video-validado.md
---
# Alcance

Correcciones de los seis hallazgos reproducidos de la revisión integral. Las
pruebas usan temporales, medios sintéticos y transporte remoto simulado. No
acreditan recuperación ante pérdida física de alimentación ni eliminan las
carreras con editores externos entre la última comprobación y replace/unlink.
Se mantienen pendientes metadata 3.3, vídeo 3.4 y entrega 2.3; no se archiva nada.

# 1. Bloqueo del origen (P1)

Las regresiones de alias de mayúsculas/Unicode y de sustitución del directorio
fallaban antes de corregir el código (cuatro fallos). El bloqueo usa dispositivo
e inode, conserva un descriptor del directorio y comprueba su identidad al
adquirirlo y antes de usarlo. Dos directorios distintos pueden trabajar a la vez;
los alias admitidos por el filesystem comparten la exclusión. Los tests omiten
con motivo un alias que el volumen no admita; en el host probado se admiten ambos.

Se conserva también el bloqueo anterior por ruta para reconocer propietarios
activos/obsoletos de esa ruta. Al actualizar, cerrar los procesos de versiones
anteriores: estas no conocen la exclusión nueva por inode para otros alias.
Se verifican la recuperación explícita del propietario obsoleto y el rechazo de
un origen reemplazado antes de adquirir el bloqueo o mientras está adquirido.
Pasaron las 212 pruebas rápidas, incluidos los seis casos nuevos de bloqueo.

# 2. Antecedentes de entrega (P1)

La regresión de tres ejecuciones fallaba: A conservaba READY, B enviaba y quedaba
UNCERTAIN y C volvía a enviar al adoptar A. Se recorren ahora todos los antecedentes
solapados, también al reanudar A. Los checkpoints numeran revisiones del job y
se comparan intento/revisión/progreso, sin ordenar progreso por UUID del run.
Estados antiguos sin revisión se tratan conservadoramente. Jobs distintos con
posible entrega solapada requieren reconciliación.

La regresión exige un solo submit simulado después de abrir C y reanudar A.
También se comprueban adopción de READY aún no enviado, entrega acreditada y
reconciliación humana posterior sin duplicar. El recorrido completo se repite con
JPEG y validadores reales; solo el cliente remoto es simulado.
Pasaron 214 pruebas rápidas y las ocho integraciones de entrega, incluidas las dos
nuevas de reanudación del propietario antiguo y apertura de otra ejecución.

# 3. Propiedad de publicación (P1)

Fallaban tres regresiones: rename rechazado con bytes idénticos y colisión tras
publish_intent de rename/substitute. La reanudación podía retirar el origen antes
de detectar que el destino era ajeno. Ahora todos los rechazos quedan registrados
y la intención persiste dispositivo/inode del temporal local antes de publicar.
El hash acredita contenido; la identidad acredita la publicación. Los hardlinks
antiguos pueden recuperarse si el enlace local sigue acreditando el mismo inode;
un reemplazo antiguo sin evidencia suficiente exige revisión.

Se prueban colisiones idénticas de rename/substitute/export, retirada explícita de
la colisión por el fixture, publicación propia interrumpida antes de confirmación
y recuperación después de retirar el enlace local. Candidatos y backups se conservan.
Pasaron 64 pruebas afectadas, la suite rápida de 220 casos y después las dos
variantes de rechazo actual/antiguo. Pasaron además 13 integraciones de interrupción
de metadata y publicación de vídeo entre volúmenes local/HFS+ sintéticos.

# 4. Autorización de reintento (P1)

La regresión fallaba porque delivery_confirmed=false renovaba una resolución ya
consumida y provocaba el tercer submit. Ahora solo una declaración explícita de
delivery_resolution crea una autorización única ligada al job y al intento
incierto. Se persiste y consume antes de habilitar el siguiente intento. Cambiar
otras decisiones o reparar exportados conserva su estado, sin renovarla.

Una autorización consumida antes de interrumpir el preflight puede completar ese
único intento al reanudar. Si vuelve a fallar, hace falta otra declaración explícita,
incluso si el valor vuelve a ser not-delivered. Las decisiones antiguas sin esa
vinculación conservan la pausa y requieren declarar de nuevo la resolución.
Las regresiones comprueban la decisión ajena, la reparación, la interrupción y
una nueva autorización válida. La integración usa JPEG/ExifTool reales y cliente
remoto simulado, con las mismas órdenes interactivas del producto.
Pasaron las 224 pruebas rápidas y las dos integraciones afectadas de reconciliación
y autorizaciones sucesivas, sin repetir una entrega por cambiar otra decisión.

# 5. Inventario del estado del uploader (P2)

Fallaban dos regresiones de subcarpeta ilegible: permisos reales y error inyectado
de scandir. El recorrido propaga ahora sus errores; tampoco se ocultan errores de
lectura/copia. La entrega permanece DELIVERED y solo el backup queda pendiente.
Al recuperar el acceso se copian y verifican los archivos omitidos, sin otro submit.

También se comprueba que un directorio legible realmente vacío sí puede producir
un backup verificado de cero archivos. La integración recorre JPEG/ExifTool y el
cliente simulado, pierde acceso al estado, sale con fallo y reanuda solo el backup.
Pasaron las 227 pruebas rápidas y las dos integraciones afectadas de fallo de copia
y directorio ilegible, sin omisiones ni repetición del envío simulado.

# 6. Línea temporal A/V (P2)

Antes de corregir, dos regresiones publicaban el candidato desplazado unos 577 ms,
tanto automático como manual. Pasaban dimensiones, duración, fechas y decode;
se retiraba el original. El caso válido de audio retardado con silencio inicial
de la ruta FFmpeg también fallaba por comparar solo las duraciones de las pistas.

La validación usa ahora los PTS y duraciones de frames decodificados después de
aplicar edit lists y skip/discard del decoder. Compara el intervalo de presentación
total y los intervalos de audio relativos al primer frame de vídeo, incluidos
huecos internos. Un desplazamiento común de todas las pistas es válido. La
tolerancia A/V es el máximo de 50 ms y dos bloques AAC según sample rate; es
independiente de la duración de un frame de vídeo lento.

La cobertura temporal distinta solo se permite tras medir todas sus muestras con
astats y acreditar silencio <= -90 dBFS. Así, el silencio inicial que añade la
ruta AAC ya verificada no se confunde con desincronización. No se presume silencio
por el contenedor ni por un promedio. La evidencia av_timing conserva intervalos,
tolerancia y medidas, sin alterar la ruta de audio ni recodificar otra vez el vídeo.

Se prueban rechazo automático/manual, AAC con padding real, edit lists presentes,
orígenes temporales distintos, vídeo que empieza después del audio y silencio
añadido legítimo. Los candidatos/operaciones pendientes con evidencia antigua
se revalidan antes de publicar, también al recuperar un resultado ready. Los
contratos rápidos prueban huecos, datos incompletos y ese caso de recuperación;
los siete casos adicionales de medios usan herramientas reales.

Es validación de estructura y tiempos de presentación, no correlación del contenido
sonoro ni aprobación perceptual. No acredita una edición interna que cambie el
contenido manteniendo los mismos intervalos. Una línea temporal ilegible o que
el productor no consiga conservar se rechaza; no se publica por confirmación humana.
Las revisiones de calidad RF y Apple Photos siguen pendientes.
Pasaron las 236 pruebas rápidas y las 72 integraciones locales conjuntas sin
omisiones; después de reforzar los fixtures se repitieron los siete casos A/V.
Los 30 casos rápidos y 11 integraciones nuevos se suman a los 206/61 anteriores.

# Reproducción y regresiones

| Hallazgo | Evidencia antes de corregir | Regresión y casos válidos próximos |
| --- | --- | --- |
| 1 — Bloqueo | Cuatro fallos: alias admitidos y origen reemplazado. | test_state: seis casos nuevos; directorios independientes, propietario antiguo y stale recovery. |
| 2 — Antecedentes | La tercera ejecución hacía el segundo submit del mismo job incierto. | Dos contratos nuevos y dos recorridos reales locales; READY sin enviar, acreditación y reconciliación. |
| 3 — Publicación | Tres fallos: colisión idéntica y retirada del origen tras intención. | Siete casos nuevos; rechazo actual/antiguo, hardlink propio, retirada del enlace y colisión revisada. |
| 4 — Reintento | delivery_confirmed=false provocaba el tercer submit. | Tres contratos nuevos y un recorrido interactivo; nonce por job/intento, interrupción y autorización nueva válida. |
| 5 — Backup | Dos recorridos omitían la subcarpeta sin fallar. | Tres contratos nuevos y un recorrido local; recuperación sin submit y estado vacío realmente legible. |
| 6 — A/V | Dos candidatos desplazados se publicaban; la ruta válida con silencio inicial se rechazaba. | Nueve contratos rápidos y siete integraciones reales; edit lists, padding, offsets comunes y revalidación antigua. |

Las pruebas de contrato simulan medios/clientes solo donde se declara; las de
ExifTool/HandBrake/FFmpeg/Pillow usan herramientas reales. Ninguna prueba acredita
autenticación, una carga remota real ni una revisión perceptual humana.
