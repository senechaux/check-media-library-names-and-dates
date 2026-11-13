## 1. Comando y etapas
- [ ] 1.1 Implementar run, --config, --dry-run, --apply y --resume sobre safe-execution.
- [ ] 1.2 Implementar orden de etapas, dependencias por archivo y selección del alcance.
- [ ] 1.3 Añadir planificación legible y aprobación única del lote, sin resolver conflictos implícitamente.

## 2. Intervención y recuperación
- [ ] 2.1 Definir estado de pausa, instrucciones por aplicación y preparación de copias identificadas.
- [ ] 2.2 Implementar comprobar/posponer/cancelar y revalidación con adaptadores de etapa.
- [ ] 2.3 Tratar EOF, ausencia de TTY, Ctrl+C y cambios de configuración sin perder estado.
- [ ] 2.4 Implementar recuperación por evidencia e informe final con códigos de salida.

## 3. Verificación e integración
- [ ] 3.1 Verificar escenarios guided-pipeline con adaptadores simulados, entradas de terminal y fallos inyectados.
- [ ] 3.2 Probar recorrido manual y reanudación con dos archivos homónimos en álbumes distintos.
- [ ] 3.3 Comprobar el recorrido de etapas con adaptadores simulados y documentar sus puntos de integración; cada cambio posterior integra su adaptador y la prueba integral pertenece a verified-export-and-delivery.
- [ ] 3.4 Actualizar OKF y README con instrucciones reales y límites comprobados.
