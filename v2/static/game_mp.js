// Frontend de la mesa multijugador (v2). Sin frameworks, fetch() liso +
// Socket.IO para push en vivo, con un poller REST independiente como
// respaldo real (no solo "por si el socket se cae": corre siempre, en
// paralelo, así los dos caminos pedidos —polling y websocket— están los
// dos activos de verdad).

const $ = (id) => document.getElementById(id);

const pantallaInicio = $("pantalla-inicio");
const pantallaAlta = $("pantalla-alta");
const pantallaLobby = $("pantalla-lobby");
const pantallaJuego = $("pantalla-juego");
const pantallaCierre = $("pantalla-cierre");

let codigoSala = null;
let salaActual = null;
let jugadorActual = null;
let ultimoEventoId = 0;
let socket = null;

function ocultarTodas() {
  [pantallaInicio, pantallaAlta, pantallaLobby, pantallaJuego, pantallaCierre].forEach((p) => {
    p.hidden = true;
  });
}

async function apiPost(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const datos = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(datos.error || `Error ${resp.status}`);
  return datos;
}

async function apiGet(url) {
  const resp = await fetch(url);
  const datos = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(datos.error || `Error ${resp.status}`);
  return datos;
}

// --- Pantalla 1: crear o unirse -------------------------------------------

$("btn-crear-sala").addEventListener("click", async () => {
  try {
    const { sala } = await apiPost("/api/salas", { modo: "historia" });
    codigoSala = sala.codigo;
    $("codigo-mostrado").textContent = codigoSala;
    ocultarTodas();
    pantallaAlta.hidden = false;
  } catch (err) {
    mostrarErrorInicio(err.message);
  }
});

$("btn-ir-a-unirse").addEventListener("click", async () => {
  const codigo = $("input-codigo-sala").value.trim().toUpperCase();
  if (!codigo) return;
  try {
    await apiGet(`/api/salas/${codigo}`);
    codigoSala = codigo;
    $("codigo-mostrado").textContent = codigoSala;
    ocultarTodas();
    pantallaAlta.hidden = false;
  } catch (err) {
    mostrarErrorInicio(err.message);
  }
});

function mostrarErrorInicio(mensaje) {
  const el = $("error-inicio");
  el.textContent = mensaje;
  el.hidden = false;
}

// --- Pantalla 2: alta de personaje -----------------------------------------

$("form-alta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const datos = new FormData(evento.target);
  const errorEl = $("error-alta");
  errorEl.hidden = true;
  try {
    const { sala, jugador } = await apiPost(`/api/salas/${codigoSala}/unirse`, {
      nombre: datos.get("nombre"),
      trasfondo: datos.get("trasfondo"),
      barrio: datos.get("barrio"),
      objetivo: datos.get("objetivo"),
    });
    salaActual = sala;
    jugadorActual = jugador;
    conectarSocket();
    iniciarPollingRespaldo();
    if (sala.estado === "en_curso") {
      await entrarAPantallaJuego();
    } else {
      mostrarLobby();
    }
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
});

// --- Pantalla 3: lobby -------------------------------------------------

function mostrarLobby() {
  ocultarTodas();
  pantallaLobby.hidden = false;
  $("lobby-codigo").textContent = salaActual.codigo;
  $("lobby-minimo").textContent = salaActual.min_jugadores;
  $("lobby-maximo").textContent = salaActual.max_jugadores;
  actualizarListaLobby();
}

async function actualizarListaLobby() {
  const { jugadores } = await apiGet(`/api/salas/${codigoSala}`);
  renderizarListaJugadores($("lobby-jugadores"), jugadores);
  const faltan = Math.max(0, salaActual.min_jugadores - jugadores.length);
  $("lobby-estado").textContent =
    faltan > 0
      ? `Esperando ${faltan} jugador(es) más para arrancar...`
      : "¡Ya se puede arrancar! Esperando confirmación del servidor...";
}

function renderizarListaJugadores(lista, jugadores) {
  lista.innerHTML = "";
  jugadores.forEach((j) => {
    const li = document.createElement("li");
    const nombre = document.createElement("span");
    nombre.textContent = j.nombre;
    if (j.es_anfitrion) nombre.classList.add("anfitrion");
    if (j.es_final) nombre.classList.add("jugador-final");
    if (!j.vivo) nombre.classList.add("jugador-muerto");
    const detalle = document.createElement("span");
    detalle.textContent = j.es_final
      ? `${j.final_tipo || "final"} · ${j.puntaje} pts`
      : `salud ${j.salud} · día ${j.capitulo}/7`;
    li.appendChild(nombre);
    li.appendChild(detalle);
    lista.appendChild(li);
  });
}

// --- Pantalla 4: partida en curso ------------------------------------------

async function entrarAPantallaJuego() {
  ocultarTodas();
  pantallaJuego.hidden = false;
  await refrescarVistaPropia();
  await refrescarMesa();
}

async function refrescarVistaPropia() {
  const { vista, jugador, sala } = await apiGet(`/api/jugadores/${jugadorActual.id}`);
  jugadorActual = jugador;
  salaActual = sala;
  renderVista(vista);
}

async function refrescarMesa() {
  const { sala, jugadores } = await apiGet(`/api/salas/${codigoSala}`);
  salaActual = sala;
  renderizarListaJugadores($("tabla-jugadores"), jugadores);
  if (sala.estado === "terminada") {
    mostrarCierre(sala, jugadores);
  }
}

function renderVista(vista) {
  const panel = vista.panel || {};
  const linea = "-".repeat(46);
  $("panel-estado").textContent =
    `${linea}\n` +
    `${panel.dia || ""}\n` +
    `Misión: ${panel.mision || ""}\n` +
    `Ubicación: ${panel.ubicacion || ""}\n` +
    `Inventario: ${panel.inventario || ""}\n` +
    `Salud: ${panel.salud || ""}\n` +
    `${linea}`;

  $("narracion").textContent = vista.narracion || "";

  const dialogosEl = $("dialogos");
  dialogosEl.innerHTML = "";
  (vista.dialogos || []).forEach(([personaje, texto]) => {
    const p = document.createElement("p");
    p.textContent = `${personaje}: "${texto}"`;
    dialogosEl.appendChild(p);
  });

  const mensajeEl = $("mensaje-efecto");
  const mensaje = vista.mensaje_efecto || vista.mensaje_libre;
  if (mensaje) {
    mensajeEl.textContent = mensaje;
    mensajeEl.hidden = false;
  } else {
    mensajeEl.hidden = true;
  }

  const bloqueFinal = $("bloque-final");
  const bloqueOpciones = $("bloque-opciones");
  if (vista.es_final) {
    bloqueOpciones.hidden = true;
    bloqueFinal.hidden = false;
    $("etiqueta-final").textContent = `FIN DE TU HISTORIA: ${vista.final_tipo || "desconocido"}`;
  } else {
    bloqueFinal.hidden = true;
    bloqueOpciones.hidden = false;
    const lista = $("lista-opciones");
    lista.innerHTML = "";
    (vista.opciones || []).forEach((texto, i) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.textContent = `[${i + 1}] ${texto}`;
      boton.addEventListener("click", () => enviarAccion({ tipo: "opcion", valor: i + 1 }));
      lista.appendChild(boton);
    });
  }
}

$("form-libre").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const input = $("input-libre");
  const texto = input.value.trim();
  if (!texto) return;
  enviarAccion({ tipo: "libre", valor: texto });
  input.value = "";
});

async function enviarAccion(cuerpo) {
  const errorEl = $("error-accion");
  errorEl.hidden = true;
  try {
    const { vista } = await apiPost(`/api/jugadores/${jugadorActual.id}/accion`, cuerpo);
    renderVista(vista);
    await refrescarMesa();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
}

function agregarAlFeed(evento) {
  const feed = $("feed-eventos");
  const li = document.createElement("li");
  li.textContent = evento.mensaje;
  li.className = `evento-${evento.tipo}`;
  feed.prepend(li);
  ultimoEventoId = Math.max(ultimoEventoId, evento.id || ultimoEventoId);
}

// --- Pantalla 5: cierre ------------------------------------------------

function mostrarCierre(sala, jugadores) {
  ocultarTodas();
  pantallaCierre.hidden = false;
  const titulo = $("cierre-titulo");
  if (sala.resultado === "derrota_colectiva") {
    titulo.textContent = "Se acabó el tiempo — nadie logró su misión. Pierde toda la mesa.";
  } else {
    const ganador = jugadores.find((j) => j.id === sala.ganador_jugador_id);
    titulo.textContent = ganador
      ? `Gana ${ganador.nombre} con ${ganador.puntaje} puntos.`
      : "La partida terminó.";
  }
  const tabla = $("cierre-tabla");
  tabla.innerHTML = "";
  [...jugadores]
    .sort((a, b) => b.puntaje - a.puntaje)
    .forEach((j) => {
      const li = document.createElement("li");
      li.textContent = `${j.nombre} — ${j.puntaje} pts (${j.final_tipo || "sin terminar"})`;
      tabla.appendChild(li);
    });
}

// --- Tiempo real: Socket.IO + polling de respaldo, los dos activos --------

function conectarSocket() {
  socket = io();
  socket.on("connect", () => {
    socket.emit("unirse_sala", { sala_id: jugadorActual.sala_id });
  });
  socket.on("actualizacion", (payload) => {
    if (payload.evento) agregarAlFeed(payload.evento);
    if (payload.sala) salaActual = payload.sala;
    if (payload.jugadores) {
      if (!pantallaLobby.hidden) {
        renderizarListaJugadores($("lobby-jugadores"), payload.jugadores);
      }
      if (!pantallaJuego.hidden) {
        renderizarListaJugadores($("tabla-jugadores"), payload.jugadores);
      }
    }
    if (payload.sala && payload.sala.estado === "en_curso" && !pantallaLobby.hidden) {
      entrarAPantallaJuego();
    }
    if (payload.sala && payload.sala.estado === "terminada" && !pantallaJuego.hidden) {
      apiGet(`/api/salas/${codigoSala}`).then(({ sala, jugadores }) => mostrarCierre(sala, jugadores));
    }
  });
}

const INTERVALO_POLLING_MS = 4000;

function iniciarPollingRespaldo() {
  setInterval(async () => {
    if (!codigoSala || !jugadorActual) return;
    try {
      const { eventos } = await apiGet(`/api/salas/${codigoSala}/eventos?desde=${ultimoEventoId}`);
      eventos.forEach(agregarAlFeed);

      if (!pantallaLobby.hidden) {
        await actualizarListaLobby();
        const { sala } = await apiGet(`/api/salas/${codigoSala}`);
        if (sala.estado === "en_curso") await entrarAPantallaJuego();
      } else if (!pantallaJuego.hidden) {
        await refrescarMesa();
      }
    } catch (err) {
      // Polling silencioso: si falla una vuelta no pasa nada, se reintenta sola.
    }
  }, INTERVALO_POLLING_MS);
}
