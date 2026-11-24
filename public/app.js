const NOMBRES_DIA = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const NOMBRE_MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const MESES_CORTOS = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.'];
const DIAS_CORTOS = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE'];
const DIAS_API = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes'];
const MOTIVOS_SUSPENSION = ['Clima', 'Emergencia personal', 'Seguridad', 'Fenómeno natural'];

let horarioActivo = null;
let materias = [];
const estado = {
  paso: 1,
  materia: '',
  fecha: '',
  tuvoSuspension: null,
  suspensiones: [],
  fechaSuspensionPendiente: null,
  motivoLibreAbierto: false,
  confirmacionMotivo: '',
  error: '',
  cargando: true,
  errorApi: '',
};

const wizard = document.querySelector('#wizard');
const stepCount = document.querySelector('#step-count');
const progressFill = document.querySelector('#progress-fill');
const progressTrack = document.querySelector('#progress-track');
const stepSteps = document.querySelector('#step-steps');

function escapar(valor) {
  return String(valor).replace(/[&<>"']/g, (caracter) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[caracter]);
}

function fechaLocalISO(fecha) {
  const year = fecha.getFullYear();
  const month = String(fecha.getMonth() + 1).padStart(2, '0');
  const day = String(fecha.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function fechaDesdeISO(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day, 12);
}

function fechaLegible(iso) {
  const fecha = fechaDesdeISO(iso);
  return `${NOMBRES_DIA[fecha.getDay()]} ${fecha.getDate()} de ${NOMBRE_MES[fecha.getMonth()]}`;
}

function fechaCorta(iso) {
  const fecha = fechaDesdeISO(iso);
  return `${fecha.getDate()} ${MESES_CORTOS[fecha.getMonth()]}`;
}

function rangoFechasAdicionales(fechas) {
  const ordenadas = [...fechas].sort();
  if (!ordenadas.length) return 'Sin fechas adicionales';
  if (ordenadas.length === 1) return fechaCorta(ordenadas[0]);
  const primera = fechaDesdeISO(ordenadas[0]);
  const ultima = fechaDesdeISO(ordenadas[ordenadas.length - 1]);
  if (primera.getMonth() === ultima.getMonth() && primera.getFullYear() === ultima.getFullYear()) {
    return `${primera.getDate()} — ${ultima.getDate()} ${MESES_CORTOS[ultima.getMonth()]}`;
  }
  return `${fechaCorta(ordenadas[0])} — ${fechaCorta(ordenadas[ordenadas.length - 1])}`;
}

function formatearHoras(horas) {
  return Number.isInteger(horas) ? String(horas) : Number(horas).toLocaleString('es-MX', { maximumFractionDigits: 1 });
}

function horasSemanales(materia) {
  return Object.values(materia.horas).reduce((suma, cantidad) => suma + cantidad, 0);
}

function materiaSeleccionada() {
  return materias.find((materia) => materia.nombre === estado.materia);
}

function convertirMaterias(datos) {
  return datos.map((materia, indice) => ({
    numero: indice + 1,
    nombre: String(materia.nombre),
    horas: Object.fromEntries(DIAS_API.map((dia, diaIndice) => [diaIndice, Number(materia.horas?.[dia] || 0)])),
    horasTotalesSemana: Number(materia.horas_totales_semana || 0),
  }));
}

function rangoEvento(evento) {
  if (evento.fecha_inicio === evento.fecha_fin) {
    return `${fechaLegible(evento.fecha_inicio)} de ${evento.fecha_inicio.slice(0, 4)}`;
  }
  return `${fechaLegible(evento.fecha_inicio)} al ${fechaLegible(evento.fecha_fin)} de ${evento.fecha_fin.slice(0, 4)}`;
}

function dibujarExclusiones(exclusiones) {
  const etiquetas = {
    suspension_laboral: 'Suspensiones laborales',
    examen_ordinario: 'Ordinarios y competencias',
    examen_extraordinario: 'Extraordinarios',
  };
  const grupos = new Map();
  for (const evento of exclusiones) {
    const etiqueta = etiquetas[evento.tipo] || evento.descripcion || 'Otras exclusiones';
    if (!grupos.has(etiqueta)) grupos.set(etiqueta, []);
    grupos.get(etiqueta).push(rangoEvento(evento));
  }
  const lista = document.querySelector('#calendar-exclusion-list');
  if (!lista) return;
  lista.innerHTML = [...grupos.entries()].map(([etiqueta, fechas]) =>
    `<li><strong>${escapar(etiqueta)}:</strong> ${fechas.map(escapar).join('; ')}.</li>`,
  ).join('') || '<li>No hay exclusiones registradas.</li>';
}

const COLUMNAS_CONSULTA = [
  { key: 'lunes', total: '#api-total-lunes', etiqueta: 'Lunes' },
  { key: 'martes', total: '#api-total-martes', etiqueta: 'Martes' },
  { key: 'miercoles', total: '#api-total-miercoles', etiqueta: 'Miércoles' },
  { key: 'jueves', total: '#api-total-jueves', etiqueta: 'Jueves' },
  { key: 'viernes', total: '#api-total-viernes', etiqueta: 'Viernes' },
];

function ponerTexto(selector, texto) {
  const elemento = document.querySelector(selector);
  if (elemento) elemento.textContent = texto;
}

function dibujarConsultaDatos(datos) {
  const filas = datos.materias.map((materia) => {
    const valores = COLUMNAS_CONSULTA.map(({ key, etiqueta }) => {
      const horas = Number(materia.horas?.[key] || 0);
      return `<td data-label="${etiqueta}">${horas > 0 ? `${formatearHoras(horas)} h` : '—'}</td>`;
    }).join('');
    return `<tr><th scope="row">${escapar(materia.nombre)}</th>${valores}<td class="api-weekly-total">${formatearHoras(Number(materia.horas_totales_semana || 0))} h</td></tr>`;
  }).join('');
  document.querySelector('#api-subject-rows').innerHTML = filas;

  const totalesPorDia = Object.fromEntries(COLUMNAS_CONSULTA.map(({ key, total }) => {
    const totalDia = datos.materias.reduce((suma, materia) => suma + Number(materia.horas?.[key] || 0), 0);
    ponerTexto(total, `${formatearHoras(totalDia)} h`);
    return [key, totalDia];
  }));
  const totalGrupo = Object.values(totalesPorDia).reduce((suma, horas) => suma + horas, 0);
  ponerTexto('#api-total-semana', `${formatearHoras(totalGrupo)} h`);

  const anio = datos.periodo.split('-')[0];
  ponerTexto('#api-data-context', `Periodo ${datos.periodo} · Grupo ${datos.grupo} · Datos consultados directamente al servidor`);
  ponerTexto('#api-data-period', `GRUPO ${datos.grupo} · ${datos.periodo}`);
  ponerTexto('#api-regular-end', `${fechaLegible(datos.fecha_fin_regular)} de ${anio}`);
  ponerTexto('#api-extra-dates', `${rangoFechasAdicionales(datos.fechas_adicionales)} de ${anio}`);
  ponerTexto('#api-final-date', `${fechaLegible(datos.fecha_fin_calculo)} de ${anio}`);

  const etiquetas = {
    suspension_laboral: 'Suspensiones laborales',
    examen_ordinario: 'Ordinarios y competencias',
    examen_extraordinario: 'Extraordinarios',
  };
  const exclusiones = Array.isArray(datos.exclusiones) ? datos.exclusiones : [];
  document.querySelector('#api-exclusion-list').innerHTML = exclusiones.length
    ? exclusiones.map((evento) => {
      const etiqueta = etiquetas[evento.tipo] || evento.descripcion || 'Otra exclusión';
      const descripcion = evento.descripcion && evento.descripcion !== etiqueta
        ? `<small>${escapar(evento.descripcion)}</small>`
        : '';
      return `<li><strong>${escapar(etiqueta)}</strong><span>${escapar(rangoEvento(evento))}</span>${descripcion}</li>`;
    }).join('')
    : '<li>No hay exclusiones registradas para este periodo.</li>';
  document.querySelector('#api-data-content').hidden = false;
}

function mostrarEstadoConsulta(mensaje, tipo = '') {
  const estadoConsulta = document.querySelector('#api-data-status');
  estadoConsulta.textContent = mensaje;
  estadoConsulta.className = `api-data-status${tipo ? ` ${tipo}` : ''}`;
  estadoConsulta.hidden = !mensaje;
}

async function actualizarConsultaDatos() {
  const dialogo = document.querySelector('#api-data-dialog');
  const botonActualizar = document.querySelector('#refresh-api-data');
  const marcaTiempo = document.querySelector('#api-data-updated');
  const yaHayDatos = !document.querySelector('#api-data-content').hidden;
  dialogo.setAttribute('aria-busy', 'true');
  botonActualizar.disabled = true;
  mostrarEstadoConsulta('Consultando los datos vigentes del API…', 'is-loading');
  try {
    const respuesta = await fetch('/api/v1/horario?grupo=932', {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    let datos;
    try {
      datos = await respuesta.json();
    } catch {
      throw new Error('El servidor no devolvió una respuesta JSON válida.');
    }
    if (!respuesta.ok) throw new Error(datos.error || 'No se pudo consultar el horario compartido.');
    if (!datos || !Array.isArray(datos.materias) || !datos.materias.length
      || !Array.isArray(datos.fechas_adicionales) || !Array.isArray(datos.exclusiones)
      || !datos.fecha_fin_regular || !datos.fecha_fin_calculo || !datos.periodo) {
      throw new Error('La respuesta de datos está incompleta.');
    }
    dibujarConsultaDatos(datos);
    const ahora = new Date();
    marcaTiempo.dateTime = ahora.toISOString();
    marcaTiempo.textContent = `Actualizado ${new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' }).format(ahora)}`;
    mostrarEstadoConsulta('Datos actualizados desde el API.', 'is-success');
  } catch (error) {
    const detalle = error instanceof Error ? error.message : 'Comprueba tu conexión e intenta de nuevo.';
    mostrarEstadoConsulta(yaHayDatos
      ? `No se pudo actualizar. La tabla conserva la consulta anterior. ${detalle}`
      : `No se pudieron cargar los datos. ${detalle}`, 'is-error');
  } finally {
    dialogo.removeAttribute('aria-busy');
    botonActualizar.disabled = false;
  }
}

const dialogoDatosApi = document.querySelector('#api-data-dialog');
const botonAbrirDatosApi = document.querySelector('#open-api-data');
botonAbrirDatosApi?.addEventListener('click', () => {
  dialogoDatosApi.showModal();
  actualizarConsultaDatos();
});
document.querySelector('#close-api-data')?.addEventListener('click', () => dialogoDatosApi.close());
document.querySelector('#refresh-api-data')?.addEventListener('click', actualizarConsultaDatos);
dialogoDatosApi?.addEventListener('click', (evento) => {
  if (evento.target === dialogoDatosApi) dialogoDatosApi.close();
});
dialogoDatosApi?.addEventListener('close', () => botonAbrirDatosApi?.focus());

function actualizarContexto(datos) {
  const periodo = datos.periodo;
  const grupo = datos.grupo;
  const year = periodo.split('-')[0];
  const setText = (selector, value) => {
    const elemento = document.querySelector(selector);
    if (elemento) elemento.textContent = value;
  };

  setText('#period-year-tag', `PERIODO ${periodo}`);
  setText('#subject-count', `${materias.length} materias`);
  setText('#group-copy', `del grupo ${grupo}`);
  setText('#intro-period', periodo);
  setText('#period-value', periodo);
  setText('#group-value', String(grupo));
  setText('#regular-date', `Hasta el ${fechaCorta(datos.fecha_fin_regular)}`);
  setText('#additional-range', rangoFechasAdicionales(datos.fechas_adicionales));
  setText('#footer-year', year);
  document.querySelector('#brand-panel')?.setAttribute('aria-label', `Marca, periodo ${periodo} y grupo ${grupo}`);
  document.querySelector('#brand-meta')?.setAttribute('aria-label', `Periodo ${periodo}, grupo ${grupo}`);
  document.title = `Horas pendientes · Grupo ${grupo}`;
  const description = document.querySelector('meta[name="description"]');
  if (description) description.content = `Calcula las horas de clase que faltan para terminar el periodo ${periodo} del grupo ${grupo}.`;
  dibujarExclusiones(datos.exclusiones);
}

function dibujarEstadoApi() {
  stepCount.textContent = estado.cargando ? 'CARGANDO DATOS' : 'SIN CONEXIÓN';
  progressFill.style.width = estado.cargando ? '20%' : '0%';
  progressTrack.setAttribute('aria-valuenow', estado.cargando ? '20' : '0');
  stepSteps.innerHTML = '';
  wizard.innerHTML = estado.cargando
    ? '<div class="api-state" role="status"><span class="api-spinner" aria-hidden="true"></span><div><strong>Cargando el horario compartido…</strong><p>Consultando materias y calendario del periodo.</p></div></div>'
    : `<div class="api-state api-state-error" role="alert"><span class="api-state-icon" aria-hidden="true">!</span><div><strong>No pudimos cargar los datos.</strong><p>${escapar(estado.errorApi || 'Comprueba tu conexión e intenta otra vez.')}</p><button class="button button-primary" id="retry-api" type="button">Reintentar</button></div></div>`;
  document.querySelector('#retry-api')?.addEventListener('click', cargarHorario);
}

async function cargarHorario() {
  estado.cargando = true;
  estado.errorApi = '';
  dibujarEstadoApi();
  try {
    const respuesta = await fetch('/api/v1/horario?grupo=932', {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.error || 'El servidor no pudo consultar el horario.');
    if (!datos || !Array.isArray(datos.materias) || !datos.materias.length
      || !Array.isArray(datos.fechas_adicionales) || !Array.isArray(datos.exclusiones)
      || !datos.fecha_fin_regular || !datos.fecha_fin_calculo || !datos.periodo) {
      throw new Error('La respuesta del horario está incompleta.');
    }
    horarioActivo = datos;
    materias = convertirMaterias(datos.materias);
    estado.cargando = false;
    actualizarContexto(datos);
    dibujar();
  } catch (error) {
    estado.cargando = false;
    estado.errorApi = error instanceof Error ? error.message : 'Comprueba tu conexión e intenta otra vez.';
    dibujarEstadoApi();
  }
}

function diasExcluidosOficiales() {
  const excluidas = new Set();
  for (const evento of horarioActivo.exclusiones) {
    const inicio = fechaDesdeISO(evento.fecha_inicio);
    const fin = fechaDesdeISO(evento.fecha_fin);
    for (const dia = new Date(inicio); dia <= fin; dia.setDate(dia.getDate() + 1)) {
      excluidas.add(fechaLocalISO(dia));
    }
  }
  return excluidas;
}

function dibujar() {
  if (!horarioActivo) return dibujarEstadoApi();
  const resultadoSinSuspensiones = estado.paso === 5 && estado.tuvoSuspension === false;
  const etapas = resultadoSinSuspensiones
    ? [{ nombre: 'Materia' }, { nombre: 'Fecha' }, { nombre: 'Resultado' }]
    : [
      { nombre: 'Materia' },
      { nombre: 'Fecha' },
      { nombre: 'Suspensiones', opcional: estado.tuvoSuspension === null },
      { nombre: 'Resultado' },
    ];
  const pasoActual = estado.paso === 5 ? etapas.length : Math.min(estado.paso, etapas.length);
  const progreso = Math.round((pasoActual / etapas.length) * 100);
  stepCount.textContent = `PASO ${String(pasoActual).padStart(2, '0')} / ${String(etapas.length).padStart(2, '0')}`;
  progressFill.style.width = `${progreso}%`;
  progressTrack.setAttribute('aria-valuenow', String(progreso));
  stepSteps.innerHTML = etapas.map((etapa, indice) => {
    const numero = indice + 1;
    const completada = numero < pasoActual;
    const actual = numero === pasoActual;
    const clase = completada ? 'is-complete' : actual ? 'is-current' : '';
    const marcador = completada ? '✓' : String(numero).padStart(2, '0');
    return `<div class="stepper-item ${clase}" role="listitem" ${actual ? 'aria-current="step"' : ''}><span class="stepper-number" aria-hidden="true">${marcador}</span><span class="stepper-text"><span class="stepper-label">${escapar(etapa.nombre)}</span>${etapa.opcional ? '<small class="stepper-hint">Opcional</small>' : ''}</span></div>`;
  }).join('');
  if (estado.paso === 1) return dibujarMateria();
  if (estado.paso === 2) return dibujarFecha();
  if (estado.paso === 3) return dibujarSuspension();
  if (estado.paso === 4) return dibujarFechasSuspension();
  return dibujarResultado();
}

function dibujarMateria() {
  wizard.innerHTML = `
    <div class="step-content">
      <div class="step-kicker">Empecemos por tu horario</div>
      <h2 class="question">¿Qué materia impartes?</h2>
      <p class="step-hint">Elige una de las ${materias.length} materias del grupo ${escapar(horarioActivo.grupo)}. Al hacer clic, pasas a la siguiente pregunta.</p>
      <div class="subject-grid" role="group" aria-label="Materias disponibles del grupo ${escapar(horarioActivo.grupo)}">
        ${materias.map((materia) => `<button type="button" class="subject-option" data-materia="${materia.numero}" aria-label="Elegir materia ${materia.numero}: ${escapar(materia.nombre)}"><span class="subject-number">${String(materia.numero).padStart(2, '0')}</span><span class="subject-copy"><strong>${escapar(materia.nombre)}</strong><small>${formatearHoras(horasSemanales(materia))} h por semana</small></span><span class="subject-arrow" aria-hidden="true">→</span></button>`).join('')}
      </div>
    </div>`;
  document.querySelectorAll('[data-materia]').forEach((boton) => boton.addEventListener('click', () => {
    const seleccionada = materias.find((materia) => materia.numero === Number(boton.dataset.materia));
    if (!seleccionada) return;
    estado.materia = seleccionada.nombre;
    estado.error = '';
    estado.paso = 2;
    dibujar();
    document.querySelector('#fecha').focus();
  }));
}

function dibujarFecha() {
  const anio = horarioActivo.periodo.split('-')[0];
  const hoy = fechaLocalISO(new Date());
  const valor = estado.fecha || (hoy.startsWith(`${anio}-`) ? hoy : '');
  wizard.innerHTML = `
    <div class="step-content">
      <div class="step-kicker">Punto de partida</div>
      <h2 class="question">¿Qué fecha es hoy?</h2>
      <p class="step-hint">El cálculo empezará desde mañana y considerará el periodo ${escapar(horarioActivo.periodo)}.</p>
      <form id="form-fecha" novalidate>
        <label class="field-label" for="fecha">Fecha de hoy</label>
        <input class="date-input" id="fecha" type="date" min="${anio}-01-01" max="${anio}-12-31" value="${escapar(valor)}" aria-describedby="error-fecha">
        <p class="field-error" id="error-fecha" role="alert">${escapar(estado.error)}</p>
        <div class="step-actions"><button class="button button-secondary" type="button" id="volver">← Cambiar materia</button><button class="button button-primary" type="submit">Continuar <span class="arrow">→</span></button></div>
      </form>
    </div>`;
  document.querySelector('#form-fecha').addEventListener('submit', (evento) => {
    evento.preventDefault();
    const fecha = document.querySelector('#fecha').value;
    if (!fecha || !fecha.startsWith(`${anio}-`)) {
      estado.error = `Selecciona una fecha válida de ${anio}.`;
      dibujarFecha();
      document.querySelector('#fecha').focus();
      return;
    }
    estado.fecha = fecha;
    estado.error = '';
    estado.paso = 3;
    dibujar();
  });
  document.querySelector('#volver').addEventListener('click', () => { estado.paso = 1; estado.error = ''; dibujar(); });
}

function dibujarSuspension() {
  wizard.innerHTML = `
    <div class="step-content">
      <div class="step-kicker">Ajuste del calendario</div>
      <h2 class="question">¿Hubo suspensión emergente confirmada?</h2>
      <p class="step-hint">Por ejemplo, una suspensión por clima u otra emergencia. Solo ingresa fechas ya confirmadas.</p>
      <form id="form-suspension" novalidate>
        <fieldset style="border:0;padding:0;margin:0"><legend class="field-label">¿Debemos excluir alguna fecha?</legend>
          <div class="choice-row">
            <label class="choice-card"><input type="radio" name="suspension" value="si" ${estado.tuvoSuspension === true ? 'checked' : ''}><span class="choice-visual"><span class="choice-icon">✓</span><span><b>Sí, hubo</b><small>Agregar fechas confirmadas</small></span></span></label>
            <label class="choice-card"><input type="radio" name="suspension" value="no" ${estado.tuvoSuspension === false ? 'checked' : ''}><span class="choice-visual"><span class="choice-icon">—</span><span><b>No hubo</b><small>Usar calendario oficial</small></span></span></label>
          </div>
        </fieldset>
        <p class="field-error" id="error-suspension" role="alert">${escapar(estado.error)}</p>
        <div class="step-actions"><button class="button button-secondary" type="button" id="volver">← Cambiar fecha</button><button class="button button-primary" type="submit">${estado.tuvoSuspension ? 'Continuar' : 'Ver resultado'} <span class="arrow">→</span></button></div>
      </form>
    </div>`;
  document.querySelectorAll('input[name="suspension"]').forEach((input) => input.addEventListener('change', () => {
    estado.tuvoSuspension = input.value === 'si';
    estado.error = '';
    document.querySelector('#form-suspension button[type="submit"]').innerHTML = `${estado.tuvoSuspension ? 'Continuar' : 'Ver resultado'} <span class="arrow">→</span>`;
  }));
  document.querySelector('#form-suspension').addEventListener('submit', (evento) => {
    evento.preventDefault();
    if (estado.tuvoSuspension === null) {
      estado.error = 'Selecciona “Sí, hubo” o “No hubo” para continuar.';
      dibujarSuspension();
      return;
    }
    estado.error = '';
    estado.paso = estado.tuvoSuspension ? 4 : 5;
    dibujar();
  });
  document.querySelector('#volver').addEventListener('click', () => { estado.paso = 2; estado.error = ''; dibujar(); });
}

function dibujarFechasSuspension() {
  const anio = horarioActivo.periodo.split('-')[0];
  const fechaPredeterminada = estado.fecha || `${anio}-01-01`;
  const fechas = estado.suspensiones.map((suspension, indice) => `<div class="date-row"><span class="suspension-entry"><strong>${escapar(fechaLegible(suspension.fecha))}</strong><small>Motivo: ${escapar(suspension.motivo)}</small></span><span><em>${escapar(suspension.fecha)}</em><button class="remove-date" type="button" data-remove="${indice}" aria-label="Eliminar suspensión del ${escapar(suspension.fecha)}">×</button></span></div>`).join('');
  const confirmacionMotivo = estado.confirmacionMotivo && !estado.fechaSuspensionPendiente
    ? `<div class="reason-confirmation" role="status" aria-live="polite"><span aria-hidden="true">✓</span> Motivo guardado: <strong>${escapar(estado.confirmacionMotivo)}</strong></div>`
    : '';
  const selectorFecha = estado.fechaSuspensionPendiente
    ? `<div class="pending-date-summary"><span>Fecha seleccionada</span><strong>${escapar(fechaLegible(estado.fechaSuspensionPendiente))}</strong></div>`
    : `<form id="form-fecha-suspendida" novalidate>
        <label class="field-label" for="fecha-suspendida">Fecha confirmada</label>
        <div class="add-date-row"><div><input class="date-input" id="fecha-suspendida" type="date" min="${anio}-01-01" max="${anio}-12-31" value="${escapar(fechaPredeterminada)}" aria-describedby="error-suspendida"></div><button class="button add-date-button" type="submit">＋ Añadir fecha</button></div>
        <p class="field-error" id="error-suspendida" role="alert">${escapar(estado.error)}</p>
      </form>`;
  const preguntaMotivo = estado.fechaSuspensionPendiente
    ? `<div class="reason-prompt">
        <div class="reason-prompt-kicker">Un motivo por cada fecha</div>
        <h3 class="reason-question">¿Cuál fue el motivo de la suspensión?</h3>
        <p class="reason-date">Fecha: ${escapar(fechaLegible(estado.fechaSuspensionPendiente))}</p>
        <div class="reason-options" role="group" aria-label="Elige el motivo de la suspensión">
          ${MOTIVOS_SUSPENSION.map((motivo, indice) => `<button class="reason-option" type="button" data-reason="${escapar(motivo)}"><span class="reason-number">${String(indice + 1).padStart(2, '0')}</span><strong>${escapar(motivo)}</strong><span class="reason-arrow" aria-hidden="true">→</span></button>`).join('')}
          <button class="reason-option reason-option-other" type="button" id="abrir-otro-motivo"><span class="reason-number">05</span><strong>Otro</strong><span class="reason-arrow" aria-hidden="true">＋</span></button>
        </div>
        ${estado.motivoLibreAbierto ? `<form id="form-otro-motivo" class="other-reason-form" novalidate><label class="field-label" for="motivo-suspendida">Escribe el motivo</label><input class="text-input" id="motivo-suspendida" type="text" maxlength="160" autocomplete="off" placeholder="Describe el motivo de la suspensión" aria-describedby="error-motivo"><p class="field-error" id="error-motivo" role="alert">${escapar(estado.error)}</p><div class="reason-actions"><button class="button button-secondary" type="button" id="cancelar-motivo">Cancelar fecha</button><button class="button button-primary" type="submit">Guardar motivo</button></div></form>` : `<div class="reason-actions"><button class="button button-secondary" type="button" id="cancelar-motivo">Cancelar fecha</button></div>`}
      </div>`
    : '';
  wizard.innerHTML = `
    <div class="step-content">
      <div class="step-kicker">Días no lectivos adicionales</div>
      <h2 class="question">¿Qué fechas de suspensión fueron confirmadas?</h2>
      <p class="step-hint">Selecciona la fecha y pulsa “Añadir fecha”. Después elige un motivo; para cada fecha se registra una sola causa.</p>
      ${selectorFecha}
      ${preguntaMotivo}
      ${confirmacionMotivo}
      <div class="date-list" aria-live="polite">${fechas || '<div class="summary-strip"><span class="summary-tag">Aún no agregas fechas emergentes.</span></div>'}</div>
      <div class="step-actions"><button class="button button-secondary" type="button" id="volver">← Atrás</button><button class="button button-primary" type="button" id="calcular" ${estado.fechaSuspensionPendiente ? 'disabled aria-disabled="true"' : ''}>Calcular horas <span class="arrow">→</span></button></div>
    </div>`;

  const guardarSuspension = (motivo) => {
    if (!estado.fechaSuspensionPendiente || !motivo) return;
    estado.suspensiones.push({ fecha: estado.fechaSuspensionPendiente, motivo });
    estado.suspensiones.sort((a, b) => a.fecha.localeCompare(b.fecha));
    estado.confirmacionMotivo = motivo;
    estado.fechaSuspensionPendiente = null;
    estado.motivoLibreAbierto = false;
    estado.error = '';
    dibujarFechasSuspension();
  };

  const formularioFecha = document.querySelector('#form-fecha-suspendida');
  if (formularioFecha) formularioFecha.addEventListener('submit', (evento) => {
    evento.preventDefault();
    const fecha = document.querySelector('#fecha-suspendida').value;
    const mensajeError = document.querySelector('#error-suspendida');
    if (!fecha || !fecha.startsWith(`${anio}-`)) {
      estado.error = `Selecciona una fecha válida de ${anio}.`;
      mensajeError.textContent = estado.error;
      document.querySelector('#fecha-suspendida').focus();
      return;
    }
    if (estado.suspensiones.some((suspension) => suspension.fecha === fecha)) {
      estado.error = 'Esa fecha ya está en la lista.';
      mensajeError.textContent = estado.error;
      document.querySelector('#fecha-suspendida').focus();
      return;
    }
    estado.fechaSuspensionPendiente = fecha;
    estado.confirmacionMotivo = '';
    estado.motivoLibreAbierto = false;
    estado.error = '';
    dibujarFechasSuspension();
  });

  document.querySelectorAll('[data-reason]').forEach((boton) => boton.addEventListener('click', () => guardarSuspension(boton.dataset.reason)));
  const botonOtroMotivo = document.querySelector('#abrir-otro-motivo');
  if (botonOtroMotivo) botonOtroMotivo.addEventListener('click', () => {
    estado.motivoLibreAbierto = true;
    estado.error = '';
    dibujarFechasSuspension();
    document.querySelector('#motivo-suspendida').focus();
  });

  const formularioOtro = document.querySelector('#form-otro-motivo');
  if (formularioOtro) {
    formularioOtro.addEventListener('submit', (evento) => {
      evento.preventDefault();
      const campoMotivo = document.querySelector('#motivo-suspendida');
      const motivo = campoMotivo.value.trim();
      const mensajeError = document.querySelector('#error-motivo');
      if (!motivo) {
        estado.error = 'Escribe el otro motivo antes de guardar la fecha.';
        mensajeError.textContent = estado.error;
        campoMotivo.focus();
        return;
      }
      guardarSuspension(motivo);
    });
    document.querySelector('#motivo-suspendida').focus();
  }

  document.querySelector('#cancelar-motivo')?.addEventListener('click', () => {
    estado.fechaSuspensionPendiente = null;
    estado.motivoLibreAbierto = false;
    estado.error = '';
    dibujarFechasSuspension();
  });
  document.querySelectorAll('[data-remove]').forEach((boton) => boton.addEventListener('click', () => {
    estado.suspensiones.splice(Number(boton.dataset.remove), 1);
    dibujarFechasSuspension();
  }));
  document.querySelector('#volver').addEventListener('click', () => { estado.fechaSuspensionPendiente = null; estado.motivoLibreAbierto = false; estado.paso = 3; estado.error = ''; dibujar(); });
  document.querySelector('#calcular').addEventListener('click', () => { if (estado.fechaSuspensionPendiente) return; estado.paso = 5; estado.error = ''; dibujar(); });
}

function calcularHoras(materia, fecha) {
  const desde = fechaDesdeISO(fecha);
  desde.setDate(desde.getDate() + 1);
  const ultima = fechaDesdeISO(horarioActivo.fecha_fin_calculo);
  const fechasExtra = new Set(horarioActivo.fechas_adicionales);
  const exclusiones = diasExcluidosOficiales();
  estado.suspensiones.forEach((suspension) => exclusiones.add(suspension.fecha));
  let regular = 0;
  let extra = 0;
  const sesiones = [];
  for (let dia = new Date(desde); dia <= ultima; dia.setDate(dia.getDate() + 1)) {
    const indiceDia = dia.getDay();
    if (indiceDia === 0 || indiceDia === 6) continue;
    const indice = (indiceDia + 6) % 7;
    const iso = fechaLocalISO(dia);
    const cantidad = materia.horas[indice] || 0;
    if (!cantidad || exclusiones.has(iso)) continue;
    if (iso <= horarioActivo.fecha_fin_regular) {
      regular += cantidad;
      sesiones.push({ fecha: iso, horas: cantidad, extra: false });
    } else if (fechasExtra.has(iso)) {
      extra += cantidad;
      sesiones.push({ fecha: iso, horas: cantidad, extra: true });
    }
  }
  return { regular, extra, total: regular + extra, sesiones };
}

function resumenHorario(materia) {
  const dias = Object.entries(materia.horas).sort(([a], [b]) => Number(a) - Number(b));
  if (!dias.length) return '<span>Sin sesiones semanales</span>';
  return dias.map(([dia, horas]) => `<span>${DIAS_CORTOS[Number(dia)]} · ${formatearHoras(horas)} h</span>`).join('');
}

function dibujarResultado() {
  const materia = materiaSeleccionada();
  if (!materia || !estado.fecha) { estado.paso = 1; return dibujar(); }
  const resultado = calcularHoras(materia, estado.fecha);
  const detalleSuspensiones = estado.suspensiones.length
    ? `<details class="result-suspensions"><summary><span>Suspensiones descontadas</span><span class="result-detail-count">${estado.suspensiones.length}</span></summary><ul class="result-suspension-list">${estado.suspensiones.map((suspension) => `<li><time datetime="${escapar(suspension.fecha)}">${escapar(fechaLegible(suspension.fecha))}</time><span>${escapar(suspension.motivo)}</span></li>`).join('')}</ul></details>`
    : '';
  const textoNota = estado.suspensiones.length
    ? 'El conteo inicia mañana. Las suspensiones oficiales y los exámenes del calendario compartido ya están descontados.'
    : 'El conteo inicia mañana; solo considera días hábiles con clase. No registraste suspensiones emergentes.';
  const textoRegular = resultado.regular === 1 ? 'hora de clase' : 'horas de clase';
  const textoTotal = resultado.total === 1 ? 'hora en total' : 'horas en total';
  const extras = rangoFechasAdicionales(horarioActivo.fechas_adicionales).toUpperCase();
  progressFill.style.width = '100%';
  wizard.innerHTML = `
    <div class="step-content result-screen">
      <div class="result-heading"><div><div class="step-kicker">Cálculo terminado</div><h2 class="question">Este es tu conteo.</h2><p class="result-subject">${escapar(materia.nombre)} <span>·</span> ${formatearHoras(horasSemanales(materia))} h por semana</p></div><span class="result-badge">${escapar(horarioActivo.periodo)}</span></div>
      <div class="total-panel"><div><small>HORAS RESTANTES</small><div class="total-number">${formatearHoras(resultado.total)} <span>h</span></div></div><div class="total-caption">${escapar(textoTotal)}<br>desde ${escapar(fechaLegible(estado.fecha))}</div></div>
      <div class="result-breakdown"><div class="result-box"><small>HASTA EL ${escapar(fechaCorta(horarioActivo.fecha_fin_regular).toUpperCase())}</small><strong>${formatearHoras(resultado.regular)} <span>h</span></strong><p>${formatearHoras(resultado.regular)} ${escapar(textoRegular)} regulares</p></div><div class="result-box extra"><small>ADICIONALES · ${escapar(extras)}</small><strong>${formatearHoras(resultado.extra)} <span>h</span></strong><p>Margen adicional del calendario</p></div></div>
      <div class="result-note"><span class="note-symbol">i</span><div class="result-note-content"><p>${escapar(textoNota)}</p>${detalleSuspensiones}</div></div>
      <div class="result-schedule" aria-label="Horario semanal de la materia">${resumenHorario(materia)}</div>
      <div class="step-actions"><button class="button button-secondary" type="button" id="editar">← Revisar respuestas</button><button class="button button-primary" type="button" id="reiniciar">Nuevo cálculo <span class="arrow">↻</span></button></div>
    </div>`;
  document.querySelector('#editar').addEventListener('click', () => { estado.paso = 1; estado.error = ''; dibujar(); });
  document.querySelector('#reiniciar').addEventListener('click', () => {
    Object.assign(estado, { paso: 1, materia: '', fecha: '', tuvoSuspension: null, suspensiones: [], fechaSuspensionPendiente: null, motivoLibreAbierto: false, confirmacionMotivo: '', error: '' });
    dibujar();
    document.querySelector('[data-materia]')?.focus();
  });
}

cargarHorario();
