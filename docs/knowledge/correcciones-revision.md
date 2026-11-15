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

# Correcciones todavía en curso

Entrega desde READY antiguo, propiedad de publicación de rename, autorización
de reintento, inventario de backup y sincronización A/V se verifican por separado.

[^tests]: [Regresiones ejecutables](../../tests/).
