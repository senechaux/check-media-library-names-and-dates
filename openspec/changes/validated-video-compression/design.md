## Context

La captura usa Fast 720p30 con PFR y muestra un vertical anamórfico de unos
405×720 visuales. Los [ajustes propuestos](../../../docs/knowledge/herramientas-externas.md)
explican por qué se propone un perfil distinto para 720×1280 vertical cuadrado.

## Decisions

1. Seleccionar tamaño >=50.000.000 bytes por defecto, con umbral configurable;
   registrar bitrate como diagnóstico, sin inventar un umbral actual. Usar estado
   y perfil aplicados para evitar recomprimir, no solo el texto `reduced_size`.
   Un marcador histórico sin manifiesto se reporta y requiere política de migración.
2. Perfil `archive-720p30`: MP4, H.264 x264, RF 22 inicial **propuesto** para
   revisar con una muestra, audio AAC estéreo para la fuente simple de la captura,
   PFR <=30, píxeles cuadrados, sin recorte ni ampliación, metadatos comunes y
   alineación A/V. Exportar el preset JSON y registrar versión/huella/opciones.
   No afirmar que RF/audio no visibles coinciden con la captura.
3. Calcular ancho/alto visibles aplicando SAR y rotación. Encajar en 1280×720
   apaisado o 720×1280 vertical y redondear dimensiones admitidas sin deformar.
   Fuente cuadrada → límite 720×720. Alternativa `height-720` conserva la política
   de altura 720 de la captura; CFR 30 será opción explícita. No pasar dimensiones
   originales para anular los límites. Verificar orientación efectiva de la salida,
   sin aplicar dos veces una rotación que el codificador ya haya aplicado.
4. Preflight detecta HDR, varias pistas, subtítulos, vídeo sin audio, entrelazado
   y contenedores no soportados. Vídeo silencioso es válido. Varias pistas/HDR
   o filtros cuyo efecto no se haya aprobado abren pausa: el perfil simple no
   puede eliminarlos o convertirlos silenciosamente. Conservar Comb Detect/Decomb
   del preset solo si corresponde y queda registrado.
5. Normalizar no MP4 como operación explícita: remux sin recodificación si los
   streams son compatibles y cumplen el objetivo; en otro caso codificar una
   sola vez combinando conversión/compresión. Nunca cambiar solo la extensión.
   La necesidad de normalizar un vídeo pequeño no depende del umbral de grandes.
6. Codificar a temporal por ID, comprobar returncode, ffprobe, decodificación
   completa con FFmpeg, duración (diferencia <=máximo de 0,1 s y dos frames de
   salida), orientación/DAR con tolerancia relativa 0,5%, SAR, perfil de FPS y
   pistas según política. Restaurar las fechas elegidas y releerlas tras comprimir.
   Una salida menor no demuestra calidad visual: revisar muestra antes del lote.
7. Exigir `0 < bytes_salida < bytes_entrada` para sustituir por compresión.
   Si no ahorra, dejar original y registrar `not_beneficial`; no reducir calidad
   en bucle. Un remux de normalización puede crecer si el plan lo distingue y
   autoriza; no registrarlo como ahorro de compresión.
8. Publicación: verificar copia del original en archivo con jerarquía, preparar
   salida validada en el volumen del álbum, publicar sin sobrescribir con sufijo
   ` reduced_size.mp4` para compresión, y solo después retirar del álbum el original
   cuya huella siga coincidiendo. Registrar cada paso y recuperar fallos usando
   backup/salida verificados. Una colisión bloquea solo ese archivo; no limpia sus
   temporales. Limpiar por ID únicamente al completar la operación.

## Risks / Trade-offs

La compresión es con pérdida y RF 22 no garantiza un tamaño; aceptar un lote
requiere revisar una muestra. Backup local y original archivado no sustituyen
un backup externo. No existe transacción de filesystem entre discos: copia
verificada y publicación en el volumen de destino son pasos recuperables.

## Migration Plan

Primero generar derivados sin sustituir; validar una muestra horizontal, vertical,
rotada y silenciosa. Después activar instalación con archivo de originales.
Los nombres homónimos y `_full_path.txt` existentes se inventarían aparte y
necesitan asociación revisada; nunca limpiar globalmente esas carpetas.
