## 1. Perfil y planificación
- [x] 1.1 Implementar selección configurable, detección real de contenedor y política de migración de marcadores históricos.
- [x] 1.2 Crear preset JSON reproducible y calcular geometría visual con rotación/SAR, perfiles verticales y PFR/CFR.
- [x] 1.3 Planificar normalización MP4 y compresión evitando recodificar dos veces; definir pausas para HDR/pistas no cubiertas.

## 2. Ejecución y publicación
- [x] 2.1 Codificar por ID con código de salida comprobado y restaurar fechas usando el servicio temporal común.
- [x] 2.2 Implementar validación de decodificación, duración, geometría, FPS, pistas, fechas y ahorro.
- [x] 2.3 Implementar archivo verificado, publicación sin sobrescrituras y retirada recuperable del original.
- [x] 2.4 Limpiar solo operaciones completadas e integrar compresión automática/manual con la etapa guiada.

## 3. Verificación
- [x] 3.1 Verificar escenarios validated-video con fixtures de orientación horizontal/vertical/rotada, SAR no cuadrado y 24/60 FPS.
- [x] 3.2 Cubrir silenciosos, HDR/múltiples pistas, salidas corruptas/mayores, MOV → MP4 y colisiones entre álbumes.
- [x] 3.3 Inyectar interrupciones en cada paso de publicación y comprobar conservación/recuperación en otro volumen.
- [ ] 3.4 Revisar muestra visual con RF propuesto antes de fijar perfil; actualizar OKF y documentar equivalencia y diferencias con la captura.
- [x] 3.5 Validar tiempos relativos A/V efectivos en automático/manual, con edit lists, padding AAC, offsets comunes y silencio añadido legítimo; rechazar desincronización antes de publicar.
- [x] 3.6 Verificar duración y cobertura de presentación de vídeo independientemente del audio, con regresiones PFR/CFR automáticas/manuales, reanudación y candidatos válidos próximos.
