## 1. Perfil y planificación
- [ ] 1.1 Implementar selección configurable, detección real de contenedor y política de migración de marcadores históricos.
- [ ] 1.2 Crear preset JSON reproducible y calcular geometría visual con rotación/SAR, perfiles verticales y PFR/CFR.
- [ ] 1.3 Planificar normalización MP4 y compresión evitando recodificar dos veces; definir pausas para HDR/pistas no cubiertas.

## 2. Ejecución y publicación
- [ ] 2.1 Codificar por ID con código de salida comprobado y restaurar fechas usando el servicio temporal común.
- [ ] 2.2 Implementar validación de decodificación, duración, geometría, FPS, pistas, fechas y ahorro.
- [ ] 2.3 Implementar archivo verificado, publicación sin sobrescrituras y retirada recuperable del original.
- [ ] 2.4 Limpiar solo operaciones completadas e integrar compresión automática/manual con la etapa guiada.

## 3. Verificación
- [ ] 3.1 Verificar escenarios validated-video con fixtures de orientación horizontal/vertical/rotada, SAR no cuadrado y 24/60 FPS.
- [ ] 3.2 Cubrir silenciosos, HDR/múltiples pistas, salidas corruptas/mayores, MOV → MP4 y colisiones entre álbumes.
- [ ] 3.3 Inyectar interrupciones en cada paso de publicación y comprobar conservación/recuperación en otro volumen.
- [ ] 3.4 Revisar muestra visual con RF propuesto antes de fijar perfil; actualizar OKF y documentar equivalencia y diferencias con la captura.
