// Frontend de "Argentina 2001". Sin frameworks: fetch() liso y actualización
// directa del DOM. Todo el estado real vive en el servidor (sesión Flask);
// acá solo pintamos lo que /api/* devuelve.

const pantallaAlta = document.getElementById("pantalla-alta");
const pantallaJuego = document.getElementById("pantalla-juego");
const formAlta = document.getElementById("form-alta");
const errorAlta = document.getElementById("error-alta");

const imagenEscena = document.getElementById("imagen-escena");
const narracionEl = document.getElementById("narracion");
const dialogosEl = document.getElementById("dialogos");
const mensajeEfectoEl = document.getElementById("mensaje-efecto");
const panelEstadoEl = document.getElementById("panel-estado");
const bloqueFinal = document.getElementById("bloque-final");
const etiquetaFinal = document.getElementById("etiqueta-final");
const bloqueOpciones = document.getElementById("bloque-opciones");
const listaOpciones = document.getElementById("lista-opciones");
const formLibre = document.getElementById("form-libre");
const inputLibre = document.getElementById("input-libre");
const errorAccion = document.getElementById("error-accion");
const btnJugarDeNuevo = document.getElementById("btn-jugar-de-nuevo");
const btnReiniciar = document.getElementById("btn-reiniciar");

const ETIQUETAS_FINAL = {
  muerte: "☠️  FIN — NO SOBREVIVISTE",
  objetivo_cumplido: "🏁 FIN — CUMPLISTE TU OBJETIVO",
  comunidad: "🤝 FIN — SALISTE ADELANTE CON EL BARRIO",
  huida: "🚌 FIN — TE FUISTE DEL GRAN BUENOS AIRES",
  solitario: "🚪 FIN — SOBREVIVISTE, SOLO",
};

async function apiPost(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body || {}),
  });
  const datos = await resp.json();
  if (!resp.ok) {
    throw new Error(datos.error || "Error desconocido");
  }
  return datos;
}

async function apiGet(url) {
  const resp = await fetch(url, { credentials: "same-origin" });
  return resp.json();
}

function mostrarPantallaJuego() {
  pantallaAlta.hidden = true;
  pantallaJuego.hidden = false;
}

function mostrarPantallaAlta() {
  pantallaJuego.hidden = true;
  pantallaAlta.hidden = false;
}

function renderVista(vista) {
  errorAccion.hidden = true;

  if (vista.imagen_url) {
    imagenEscena.src = vista.imagen_url;
    imagenEscena.hidden = false;
  } else {
    imagenEscena.hidden = true;
    imagenEscena.removeAttribute("src");
  }

  narracionEl.textContent = vista.narracion;

  dialogosEl.innerHTML = "";
  (vista.dialogos || []).forEach(([personaje, texto]) => {
    const p = document.createElement("p");
    const nombre = document.createElement("strong");
    nombre.textContent = `${personaje}: `;
    const cita = document.createElement("span");
    cita.className = "texto-dialogo";
    cita.textContent = `"${texto}"`;
    p.appendChild(nombre);
    p.appendChild(cita);
    dialogosEl.appendChild(p);
  });

  if (vista.mensaje_efecto) {
    mensajeEfectoEl.textContent = vista.mensaje_efecto;
    mensajeEfectoEl.hidden = false;
  } else if (vista.mensaje_libre) {
    mensajeEfectoEl.textContent = vista.mensaje_libre;
    mensajeEfectoEl.hidden = false;
  } else {
    mensajeEfectoEl.hidden = true;
  }

  const panel = vista.panel;
  const linea = "-".repeat(50);
  panelEstadoEl.textContent =
    `${linea}\n` +
    `📍 Ubicación: ${panel.ubicacion}\n` +
    `🎒 Inventario/Recursos: ${panel.inventario}\n` +
    `⚠️  Estado/Salud: ${panel.salud}\n` +
    `${linea}`;

  if (vista.es_final) {
    bloqueOpciones.hidden = true;
    bloqueFinal.hidden = false;
    etiquetaFinal.textContent = ETIQUETAS_FINAL[vista.final_tipo] || "FIN DE LA PARTIDA";
  } else {
    bloqueFinal.hidden = true;
    bloqueOpciones.hidden = false;
    listaOpciones.innerHTML = "";
    vista.opciones.forEach((texto, i) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.textContent = `[${i + 1}] ${texto}`;
      boton.addEventListener("click", () => enviarOpcion(i + 1));
      listaOpciones.appendChild(boton);
    });
    inputLibre.value = "";
  }
}

async function enviarOpcion(indice) {
  try {
    const { vista } = await apiPost("/api/accion", { tipo: "opcion", valor: indice });
    renderVista(vista);
  } catch (err) {
    mostrarErrorAccion(err.message);
  }
}

async function enviarAccionLibre(texto) {
  try {
    const { vista } = await apiPost("/api/accion", { tipo: "libre", valor: texto });
    renderVista(vista);
  } catch (err) {
    mostrarErrorAccion(err.message);
  }
}

function mostrarErrorAccion(mensaje) {
  errorAccion.textContent = mensaje;
  errorAccion.hidden = false;
}

formAlta.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  errorAlta.hidden = true;
  const datos = new FormData(formAlta);
  const cuerpo = {
    nombre: datos.get("nombre"),
    trasfondo: datos.get("trasfondo"),
    barrio: datos.get("barrio"),
    objetivo: datos.get("objetivo"),
  };
  try {
    const { vista } = await apiPost("/api/nueva_partida", cuerpo);
    mostrarPantallaJuego();
    renderVista(vista);
  } catch (err) {
    errorAlta.textContent = err.message;
    errorAlta.hidden = false;
  }
});

formLibre.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const texto = inputLibre.value.trim();
  if (!texto) return;
  enviarAccionLibre(texto);
});

btnJugarDeNuevo.addEventListener("click", async () => {
  await apiPost("/api/reiniciar", {});
  formAlta.reset();
  mostrarPantallaAlta();
});

btnReiniciar.addEventListener("click", async () => {
  if (!confirm("¿Seguro que querés abandonar esta partida y empezar de nuevo?")) return;
  await apiPost("/api/reiniciar", {});
  formAlta.reset();
  mostrarPantallaAlta();
});

// Al cargar la página, si ya había una partida en curso en esta sesión
// (por ejemplo, el usuario recargó el navegador), la retomamos donde estaba.
(async function inicializar() {
  try {
    const datos = await apiGet("/api/estado");
    if (datos.activo) {
      mostrarPantallaJuego();
      renderVista(datos.vista);
    }
  } catch (err) {
    // Si falla, simplemente arrancamos desde la pantalla de alta de personaje.
  }
})();
