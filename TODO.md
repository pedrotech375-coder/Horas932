# Entregables

- [x] Cálculo de horas del grupo 932 con el calendario 2026
  - Calcular las sesiones desde el día siguiente a la fecha ingresada, solo de lunes a viernes y usando las horas diarias de cada materia.
  - Considerar el periodo regular hasta el 30 de noviembre de 2026 y como fechas adicionales el 9, 10 y 11 de diciembre de 2026.
  - Excluir las suspensiones laborales del calendario; ordinarios/competencias del 30 de noviembre al 8 de diciembre de 2026; extraordinarios del 14 al 17 de diciembre de 2026; el 18 de diciembre de 2026; y las suspensiones emergentes confirmadas.
  - Mostrar horas regulares, adicionales y total.

- [x] Elegir materia con un clic en la página y por número en Python
  - En la página, mostrar las siete materias como opciones seleccionables y avanzar al siguiente paso al hacer un clic.
  - En Python, enumerar las materias de `materias_932`, aceptar el número válido y volver a preguntar ante un número fuera de rango.
  - Mantener el mismo orden de materias en la página y en Python, usando el orden de la tabla SQL.

- [x] Elegir el motivo de cada suspensión confirmada
  - Después de seleccionar una fecha y pulsar “Añadir fecha” en la página, mostrar “Clima”, “Emergencia personal”, “Seguridad”, “Fenómeno natural” y “Otro”.
  - “Otro” abre un campo de texto y exige contenido antes de guardar la fecha; cada motivo aparece junto a su fecha y en el resultado.
  - En Python, enumerar los cuatro motivos estándar y ofrecer “Otro” con entrada de texto para cada fecha.

- [x] Mostrar claramente el progreso y la acción actual
  - Añadir un indicador con etiquetas de paso y estado actual/completado.
  - Adaptar el recorrido: si no hubo suspensión, mostrar tres pasos (materia, fecha y resultado); si sí hubo, mostrar cuatro (materia, fecha, suspensión y resultado).
  - Mantener una acción principal clara en cada paso, incluidas las opciones de continuar, volver y revisar respuestas.

- [x] Simplificar el calendario y el resultado sin ocultar datos importantes
  - Mantener visibles el límite regular del 30 de noviembre y las fechas adicionales del 9 al 11 de diciembre.
  - Colocar los detalles de exclusiones en un desplegable inicialmente cerrado: suspensiones del 2 y 16 de noviembre y 18 de diciembre; ordinarios/competencias del 30 de noviembre al 8 de diciembre; extraordinarios del 14 al 17 de diciembre.
  - En el resultado, priorizar el total y separar las horas regulares y adicionales; mostrar fechas y motivos de suspensiones en un detalle desplegable.
  - Después de guardar un motivo, mostrar una confirmación breve y clara.

- [x] Mejorar legibilidad, interacción táctil y uso móvil
  - Aumentar el tamaño del texto de preguntas, instrucciones, opciones y etiquetas principales.
  - Hacer que las tarjetas y botones tengan áreas de interacción cómodas, foco de teclado visible y etiquetas accesibles.
  - En móvil, apilar contenido, conservar el orden lógico y evitar desbordamiento horizontal.

- [x] Mantener la presentación del proyecto
  - Conservar la interfaz educativa, la columna de marca junto al título y el panel de calendario junto al asistente.

- [x] Mantener MySQL como fuente compartida de horarios y calendario
  - La base gestionada MySQL conserva los siete horarios actuales en `materias_932`, incluyendo Programación con lunes 2 h, martes 2 h y jueves 2 h.
  - Las tablas compartidas incluyen grupo 932, periodo 2026-2 activo, límite regular 30 de noviembre, fechas adicionales 9–11 de diciembre, suspensiones laborales 2 y 16 de noviembre y 18 de diciembre, y periodos de exámenes 30 de noviembre–8 de diciembre y 14–17 de diciembre.
  - La carga inicial es idempotente y no borra ni restablece cambios existentes al reiniciar.
  - La API es pública y de solo lectura; las suspensiones emergentes ingresadas para un cálculo no se convierten en cambios globales.

- [x] Consumir desde la página y Python el mismo API de horarios
  - La página carga materias, periodo y calendario desde `GET /api/v1/horario?grupo=932` y muestra estados de carga, error y reintento.
  - Python consulta el API con `urllib`, conserva selección numerada de materia y motivo, y ofrece SQLite cuando no hay conexión.
  - El API también dispone de `GET /api/health`; el DSN MySQL no se expone al navegador ni se guarda en el paquete local.

- [x] Publicar la versión inicial conectada con confirmación explícita
  - El checkpoint `576f175` fue confirmado por la usuaria; la versión Node se publicó en el dominio público después de su autorización.
  - `publishing.auto_publish` permanece desactivado; cambios posteriores no se publican automáticamente.

- [x] Sustituir el backend web Node.js por Python/FastAPI
  - Implementar `main.py` con `GET /api/v1/horario?grupo=932`, `periodo=...` opcional y `GET /api/health`, conservando el contrato JSON que consumen `public/app.js` y el programa Python.
  - Validar parámetros, usar consultas MySQL parametrizadas y mantener una API de solo lectura con errores JSON claros; no exponer `DATABASE_URL` ni aceptar escrituras públicas.
  - Reemplazar la conexión y el ejecutor de migraciones Node por Python/PyMySQL, reutilizando `horas932_migrations`, `GET_LOCK` y los SQL ya aplicados, sin reinicializar los datos.
  - Mantener intactos el frontend, el cálculo de la página, la selección de materia y la captura local de suspensiones.

- [x] Sincronizar en una sola dirección el SQLite local desde MySQL
  - En cada ejecución con API disponible, validar el JSON y, en una transacción SQLite, actualizar `materias_932`, conservar el calendario recibido y registrar grupo, periodo y última sincronización.
  - MySQL es la fuente oficial: los cambios locales de SQLite no se envían ni se aplican en MySQL; las respuestas y suspensiones de un cálculo no se guardan.
  - Si la actualización del archivo local falla pero la consulta al API funciona, continuar con la respuesta vigente e informar que la caché no se actualizó.
  - Sin conexión, ofrecer el periodo solicitado si está en caché; sin periodo explícito, usar la sincronización más reciente. Si no existe una caché previa, permitir el respaldo incluido 2026-2 con aviso; no sustituir silenciosamente un periodo explícito ausente por otro.

- [x] Cambiar el contenedor y conservar el build estático del frontend
  - Instalar versiones Python fijadas para FastAPI, Uvicorn y PyMySQL; ejecutar FastAPI en `0.0.0.0`, honrar `PORT` y usar 3000 por defecto.
  - Mantener npm únicamente para el build de `public/` a `dist/`; enrutar `/api/*` al contenedor Python y el resto al sitio estático con las rutas Webdev existentes.
  - Mantener `/api/health` como health path y `DATABASE_URL` solo en runtime; probar Preview y la conexión a MySQL sin cambiar datos compartidos.

- [x] Actualizar documentación y paquete local
  - Explicar que FastAPI es el backend de la web y que Node/npm solo compila el frontend.
  - Explicar MySQL como fuente oficial y la actualización de SQLite desde el API; actualizar la guía distribuida.
  - Regenerar `algoritmo_932_python_sql.zip` con el script, `materias_932.db` y la guía actualizada.

- [x] Guardar el nuevo checkpoint y publicar FastAPI solo tras autorización explícita
  - Subir el nuevo backend a la rama canónica `main` como `2985b52`, confirmar el SHA con la usuaria y conservar `publishing.auto_publish=false`.
  - La usuaria confirmó que veía `2985b52` y autorizó su publicación; el despliegue concluyó con estado `published` en el dominio público, manteniendo su visibilidad pública.


- [x] Añadir una consulta visual de solo lectura para mostrar los datos al profesor
  - Mostrar en la página principal un botón “Consultar datos del grupo” que abra un diálogo accesible sin interrumpir el cálculo.
  - Al abrir y al pulsar “Actualizar datos”, consultar `GET /api/v1/horario?grupo=932` desde el mismo origen con caché desactivada; no incluir ni pedir credenciales de MySQL.
  - Mostrar el periodo y grupo activos, las siete materias en una tabla con horas de lunes a viernes y total semanal, además del límite regular, fechas adicionales y exclusiones del calendario.
  - Indicar que el contenido procede del API y es de solo lectura, mostrar el momento de actualización, y ofrecer estados de carga, error y reintento.
  - Hacer que el diálogo sea usable con teclado y lector de pantalla, adaptable a móvil y con desplazamiento horizontal confinado a la tabla cuando sea necesario. No permitir editar MySQL ni guardar respuestas del cálculo.

- [ ] Guardar un checkpoint de esta consulta y pedir autorización antes de publicarla
  - Subir el cambio a `main`, confirmar el SHA guardado y conservar `publishing.auto_publish=false`.
  - No actualizar el dominio público hasta que la usuaria autorice explícitamente la publicación de esta nueva versión.
