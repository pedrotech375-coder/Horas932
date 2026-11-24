# Horas 932 — cálculo conectado

La aplicación consulta un solo horario y calendario compartidos para el grupo 932. La selección del profesor, la fecha y las suspensiones emergentes se procesan en la página; las respuestas de cálculo no se guardan.

## Stack

- **Frontend:** HTML semántico, CSS responsive y JavaScript sin framework en `Frontend/`.
- **Backend web publicado:** Python 3.12 con FastAPI y Uvicorn ASGI (`main.py` (raíz)). PyMySQL conecta el servidor con la base gestionada.
- **API:** JSON de solo lectura en `/api/v1/horario` y estado del servicio/base en `/api/health`.
- **Base de datos oficial:** MySQL administrado por Webdev. MySQL es un servicio remoto, no el archivo `Base de datos/materias_932.db`. `DATABASE_URL` solo se lee en el servidor; no aparece en el navegador ni en el paquete local. La conexión usa TLS y verifica el certificado del servidor.
- **Base local:** `Base de datos/materias_932.db` es SQLite, un archivo distinto que Python actualiza desde el API. Conserva la tabla `materias_932` y agrega `calendario_932` y `horario_cache` para fechas, periodo y hora de sincronización.
- **Programa local:** Python 3 y `urllib` estándar consultan el mismo API por HTTPS. No requiere credenciales ni dependencias de MySQL.
- **Build/publicación:** Node/npm se usa únicamente para copiar y construir los archivos estáticos de `Frontend/` en `dist/`; el backend web objetivo no es Node.
- **Rutas Webdev:** el mapa gestionado enruta `/api/*` al contenedor Python y `/*` al sitio estático; `Frontend/manus-routes.json` declara las páginas del sitio (solo `/`), no las rutas API.

## Flujo de datos

1. La página solicita `GET /api/v1/horario?grupo=932` y recibe el periodo activo, las materias con horas por día, fechas adicionales y exclusiones oficiales.
2. Se puede enviar `periodo=2026-2` para pedir un periodo específico. Sin periodo, el API devuelve el único marcado como activo para el grupo.
3. JavaScript dibuja los datos recibidos y calcula las horas en el navegador. Las suspensiones emergentes de un cálculo no se mandan al servidor ni se guardan.
4. Cada vez que se ejecuta el programa Python, consulta el API. Si la respuesta es válida, actualiza SQLite de manera transaccional y calcula con esos datos actuales. La dirección es **MySQL → API → SQLite**; no existe sincronización inversa.
5. Si el API no está disponible, Python pregunta antes de continuar con la última copia local sincronizada. Si nunca hubo sincronización, la base incluida ofrece el respaldo 2026-2 y muestra que podría estar desactualizado.

La caché SQLite es un respaldo del cliente local; no es el origen oficial de la página. Si el archivo SQLite no se puede escribir, Python todavía puede calcular con los datos vigentes que recibió del API e informa que no actualizó la caché. Si se solicita offline un periodo concreto que no está guardado localmente, no se usa silenciosamente otro periodo.

## Datos compartidos

Las migraciones versionadas están en `Base de datos/`. FastAPI las revisa al iniciar y reutiliza el historial MySQL `horas932_migrations` con el bloqueo `GET_LOCK`; la migración inicial ya aplicada no se repite. El backend no restablece el esquema ni duplica las materias.

La API es de solo lectura. Para cambiar horarios, calendario o semestre se prepara y revisa una nueva migración SQL versionada. Para activar otro periodo, esa migración añade periodo, materias y calendario, deja el periodo anterior inactivo y activa el nuevo. No hay panel público ni endpoint para escribir horarios.

El servicio MySQL de Preview y producción es el mismo. Las respuestas de MySQL se usan para actualizar el archivo local, pero esa copia nunca escribe en el servicio compartido. Las respuestas de los profesores y las suspensiones emergentes de una ejecución tampoco se almacenan.

## Ejecutar el programa Python local

El algoritmo está en `backend/calcular_horas_932.py` y la copia SQLite en `Base de datos/materias_932.db`. Python 3 no requiere instalar paquetes:

```bash
python backend/calcular_horas_932.py
```

En Windows también puedes usar `py backend/calcular_horas_932.py`. Este paquete está fijado al grupo 932. La URL del API puede cambiarse con `HORAS932_API_BASE_URL`; `HORAS932_PERIODO` solicita un periodo específico. Sin esa variable, se consulta el periodo activo. El backend FastAPI ya está publicado en https://horas932-3rxpt5kn.manus.space y ofrece el mismo contrato JSON que consume el programa local.

Para probar contra el Preview local, usa `HORAS932_API_BASE_URL=http://localhost:3000`. No copies `DATABASE_URL` al programa, a un archivo compartido ni a SQLite.

## Ejecutar el sitio local

El backend web requiere `DATABASE_URL` y las dependencias del archivo `requirements.lock`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm ci
npm run build
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 3000
```

`npm run build` crea `dist/`, la salida estática. Uvicorn inicia FastAPI en el puerto 3000; `/api/health` verifica una consulta a MySQL. En producción, Webdev dirige `/api/*` al contenedor FastAPI y sirve `dist/` desde el host estático.
