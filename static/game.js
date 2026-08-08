// Frontend de "Argentina 2001". Sin frameworks: fetch() liso y actualización
// directa del DOM. Todo el estado real vive en el servidor (sesión Flask);
// acá solo pintamos lo que /api/* devuelve.

const pantallaIntro = document.getElementById("pantalla-intro");
const introCapaCalle = document.getElementById("intro-capa-calle");
const introCapaExplosion = document.getElementById("intro-capa-explosion");
const introCapaAereo = document.getElementById("intro-capa-aereo");
const introCargando = document.getElementById("intro-cargando");
const btnSaltarIntro = document.getElementById("btn-saltar-intro");

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

// --- Cutscene de apertura ---------------------------------------------
// Tiene que coincidir con var(--duracion-intro) de static/style.css.
const DURACION_INTRO_MS = 6500;
let introTimeoutId = null;

function prefiereMovimientoReducido() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function finalizarIntro() {
  if (introTimeoutId) {
    clearTimeout(introTimeoutId);
    introTimeoutId = null;
  }
  sessionStorage.setItem("introVista", "1");
  pantallaIntro.classList.remove("intro-reproduciendo");
  pantallaIntro.hidden = true;
  mostrarPantallaAlta();
}

function precargarImagen(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(url);
    img.onerror = () => reject(new Error(`no se pudo cargar ${url}`));
    img.src = url;
  });
}

function esperar(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function precargarConReintento(url, intentos = 3, esperaMs = 1500) {
  for (let intento = 1; intento <= intentos; intento++) {
    try {
      return await precargarImagen(url);
    } catch (err) {
      if (intento === intentos) throw err;
      await esperar(esperaMs);
    }
  }
}

// Pollinations.ai (plan gratuito) solo permite 1 request en cola por IP:
// pedir las tres imágenes en paralelo dispara "Too Many Requests". Hay que
// pedirlas una por una, en secuencia.
async function precargarSecuencial(urls) {
  const resultados = [];
  for (const url of urls) {
    resultados.push(await precargarConReintento(url));
  }
  return resultados;
}

function esperarConTimeout(promesa, ms) {
  return Promise.race([
    promesa,
    new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
  ]);
}

async function reproducirIntro() {
  if (sessionStorage.getItem("introVista") === "1" || prefiereMovimientoReducido()) {
    pantallaIntro.hidden = true;
    mostrarPantallaAlta();
    return;
  }

  pantallaIntro.hidden = false;
  introCargando.hidden = false;

  let frames;
  try {
    frames = await apiGet("/api/intro");
  } catch (err) {
    pantallaIntro.hidden = true;
    mostrarPantallaAlta();
    return;
  }

  // Cada imagen puede tardar varios segundos en generarse y se piden de a
  // una (ver precargarSecuencial). Si tarda demasiado o falla, saltamos
  // directo al menú en vez de dejar al jugador esperando indefinidamente.
  try {
    await esperarConTimeout(
      precargarSecuencial([frames.calle, frames.explosion, frames.aereo]),
      45000,
    );
  } catch (err) {
    pantallaIntro.hidden = true;
    introCargando.hidden = true;
    mostrarPantallaAlta();
    return;
  }

  introCapaCalle.style.backgroundImage = `url("${frames.calle}")`;
  introCapaExplosion.style.backgroundImage = `url("${frames.explosion}")`;
  introCapaAereo.style.backgroundImage = `url("${frames.aereo}")`;
  introCargando.hidden = true;

  // Forzar reflow para que el navegador registre el estado inicial antes de
  // agregar la clase que dispara las animaciones (si no, a veces no arrancan).
  void pantallaIntro.offsetWidth;
  pantallaIntro.classList.add("intro-reproduciendo");
  introTimeoutId = setTimeout(finalizarIntro, DURACION_INTRO_MS);
}

btnSaltarIntro.addEventListener("click", finalizarIntro);

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

// Al cargar la página: si ya había una partida en curso en esta sesión (por
// ejemplo, recargaste el navegador), la retomamos directo, sin repetir la
// cutscene. Si no, mostramos la intro y de ahí pasamos al alta de personaje.
(async function inicializar() {
  let datos = null;
  try {
    datos = await apiGet("/api/estado");
  } catch (err) {
    datos = null;
  }

  if (datos && datos.activo) {
    sessionStorage.setItem("introVista", "1");
    pantallaIntro.hidden = true;
    mostrarPantallaJuego();
    renderVista(datos.vista);
    return;
  }

  reproducirIntro();
})();
