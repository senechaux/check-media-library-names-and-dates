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

# Correcciones todavía en curso

Autorización
de reintento, inventario de backup y sincronización A/V se verifican por separado.

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

[^tests]: [Regresiones ejecutables](../../tests/).
