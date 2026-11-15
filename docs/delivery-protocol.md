# Protocolo de entrega configurada v1

El transporte se habilita explícitamente. Un cliente local de confianza debe
limitarse al manifiesto; este protocolo no es una adaptación automática de
gphotos-uploader-cli. No se ha probado ninguna cuenta ni carga real.

Ejemplo alternativo de configuración, con un adaptador que implemente el contrato:

```toml
[pipeline.modes]
delivery = "auto"

[delivery]
mode = "configured-cli"
allow_cli = true
target = "alias-no-secreto"
executable = "/ruta/adaptador-con-alcance"
args = ["submit", "{scope}", "{receipts}", "{state}"]
capability_args = ["--capabilities"]
auth_args = ["--auth-check"]
state_dir = "/ruta/estado-uploader"
backup_dir = "/ruta/backup-estado"
require_capture_date = true
```

Las rutas son relativas al TOML o absolutas. State/backup deben ser disjuntos de
source/workspace/archive/export y entre sí. No incluir secretos en argumentos o
TOML. Solo se admiten placeholders scope, receipts, state y job. La lista se pasa
sin shell; no se usa expansión del shell ni se publican stdout/stderr del cliente.

`capability_args` debe devolver por stdout JSON:

```json
{"protocol":"media-library-delivery-v1","scope":"manifest-only","version":"1.0.0","simulated":false}
```

Solo tras acreditar capacidad se ejecuta `auth_args`, que devuelve:

```json
{"authenticated":true,"scope_limited":true,"target":"alias-no-secreto"}
```

Son declaraciones del cliente, no comprobaciones independientes de una cuenta.
El alias debe coincidir con la configuración. Un binario incompatible se rechaza
antes de ejecutar el preflight de autenticación o submit.

`scope.json` contiene protocol, job_id y files. Cada archivo conserva file_id,
identidad lógica, receta, ruta relativa, hash y `path` a la copia aprobada. El
cliente solo puede enviar esos paths tras comprobar sus hashes; no debe recorrer
otras carpetas ni borrar archivos. `source_export` conserva la correspondencia
con el exportado auditado; ninguna ruta del archivo de originales forma parte
del alcance. Para gphotos haría falta un wrapper revisado que genere una
configuración aislada con exactamente ese árbol y sin otros jobs.

Si el adaptador proporciona recibos, los escribe en `{receipts}`:

```json
{"protocol":"media-library-delivery-v1","job_id":"id-del-job","receipts":[{"file_id":"id-del-archivo","sha256":"hash-local-completo","remote_id":"identificador-del-cliente"}]}
```

Se exige el conjunto completo, sin duplicados, con job/ID/hash exactos. No incluir
tokens ni campos extra por archivo. El programa registra esos comprobantes como
`client_receipts` y mantiene `remote_presence_verified=false`; no consulta la API.
Sin recibos completos, cero solo acredita el comando y abre pausa de declaración.

La intención SUBMITTING se sincroniza antes de llamar al cliente. Timeout,
interrupción o resultado incierto conserva la pausa y nunca reinicia submit
automáticamente. Revisar el cliente/recibos y declarar delivered o not-delivered;
esta última resolución permite un intento, no reintentos ilimitados. El alias
y la identidad/huella del alcance protegen también entre ejecuciones.

DELIVERED se persiste antes de respaldar el estado. Un fallo posterior reintenta
el backup y no submit. Las copias privadas verificadas y su recibo se conservan;
si cambian, la ejecución requiere revisión. Los tests de este contrato usan
exclusivamente un script Python local simulado, sin red ni cuentas.
