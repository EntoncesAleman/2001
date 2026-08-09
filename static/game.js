// Frontend de "2001: Odisea en Buenos Aires". Sin frameworks: fetch() liso y actualización
// directa del DOM. Todo el estado real vive en el servidor (sesión Flask);
// acá solo pintamos lo que /api/* devuelve.

// --- Tipeo estilo "máquina de escribir" (tipo Carmen Sandiego) ----------
// El clic no es un sample de audio: es un blip sintetizado con Web Audio
// API (oscilador + envolvente corta), así no depende de ningún archivo ni
// de derechos de autor de ningún sonido real.

const VELOCIDAD_TIPEO_MS = 16;
let audioCtxTipeo = null;
let tipeoEnCurso = null;

function obtenerAudioCtxTipeo() {
  if (!audioCtxTipeo) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audioCtxTipeo = new Ctx();
  }
  return audioCtxTipeo;
}

function reproducirClicTipeo() {
  try {
    const ctx = obtenerAudioCtxTipeo();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.value = 650 + Math.random() * 350;
    gain.gain.setValueAtTime(0.05, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.02);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.03);
  } catch (err) {
    // Sin Web Audio disponible: sigue andando todo, simplemente sin clic.
  }
}

// Tipea `texto` dentro de `elemento` caracter por caracter. Clickear el
// elemento mientras tipea lo completa al instante (para no obligar a nadie
// a esperar). Cancela cualquier tipeo anterior todavía en curso.
function tipearTexto(elemento, texto) {
  if (tipeoEnCurso) {
    tipeoEnCurso.cancelado = true;
  }
  const esteTipeo = { cancelado: false };
  tipeoEnCurso = esteTipeo;

  elemento.textContent = "";
  elemento.classList.add("tipeable");

  return new Promise((resolve) => {
    function terminar(textoFinal) {
      elemento.removeEventListener("click", completarInstantaneo);
      if (tipeoEnCurso === esteTipeo) tipeoEnCurso = null;
      elemento.textContent = textoFinal;
      resolve();
    }

    function completarInstantaneo() {
      if (esteTipeo.cancelado) return;
      esteTipeo.cancelado = true;
      terminar(texto);
    }

    // Se cuelga del objeto (no solo del listener de click) para que la
    // barra espaciadora también pueda completarlo desde afuera, sin tener
    // acceso a este closure — ver el listener global de "keydown" más abajo.
    esteTipeo.completar = completarInstantaneo;

    elemento.addEventListener("click", completarInstantaneo);

    let i = 0;
    function paso() {
      if (esteTipeo.cancelado) return;
      if (i >= texto.length) {
        terminar(texto);
        return;
      }
      elemento.textContent += texto[i];
      if (texto[i].trim() !== "") reproducirClicTipeo();
      i += 1;
      setTimeout(paso, VELOCIDAD_TIPEO_MS);
    }
    paso();
  });
}

// Atajo para el que se cansa del sonido de máquina de escribir: la barra
// espaciadora completa al instante el tipeo en curso, igual que el click
// sobre el texto. No se activa si el foco está en un campo de texto (ahí
// espacio tiene que escribir un espacio) ni en un botón (ahí espacio ya
// significa "clickear este botón", no queremos pisar eso).
document.addEventListener("keydown", (evento) => {
  if (evento.code !== "Space" && evento.key !== " ") return;
  const activo = document.activeElement;
  const enCampoInteractivo = activo && ["INPUT", "TEXTAREA", "BUTTON"].includes(activo.tagName);
  if (enCampoInteractivo) return;
  if (tipeoEnCurso && !tipeoEnCurso.cancelado) {
    evento.preventDefault();
    tipeoEnCurso.completar();
  }
});

const pantallaIntro = document.getElementById("pantalla-intro");
const introCapaCalle = document.getElementById("intro-capa-calle");
const introCapaHelicoptero = document.getElementById("intro-capa-helicoptero");
const introCargando = document.getElementById("intro-cargando");
const btnSaltarIntro = document.getElementById("btn-saltar-intro");
const introMusica = document.getElementById("intro-musica");
const btnActivarSonido = document.getElementById("btn-activar-sonido");

const pantallaModo = document.getElementById("pantalla-modo");
const btnModoHistoria = document.getElementById("btn-modo-historia");
const btnModoLibre = document.getElementById("btn-modo-libre");
const modoLibreNoDisponible = document.getElementById("modo-libre-no-disponible");

const pantallaAlta = document.getElementById("pantalla-alta");
const pantallaJuego = document.getElementById("pantalla-juego");
const formAlta = document.getElementById("form-alta");
const errorAlta = document.getElementById("error-alta");

let modoElegido = "historia";

const imagenEscena = document.getElementById("imagen-escena");

// Pollinations a veces devuelve error (rate-limit u otro hipo transitorio) en
// un turno normal, no solo en la intro. Sin este manejo, la imagen queda rota
// (ícono de imagen caída) sin que el jugador entienda qué pasó. Reintentamos
// una vez con un parámetro para evitar caché, y si vuelve a fallar la
// ocultamos prolijamente en vez de dejar el ícono roto.
let imagenReintentada = false;
imagenEscena.addEventListener("error", () => {
  // Ojo acá: `imagenEscena.src` (la propiedad) resuelve a la URL absoluta
  // de la página misma cuando no hay atributo `src` puesto, así que da
  // "verdadero" igual y este chequeo no alcanza para descartar un error
  // espurio en un turno sin imagen. `getAttribute("src")` sí devuelve null
  // en ese caso.
  if (!imagenEscena.getAttribute("src") || imagenEscena.hidden) return;
  if (!imagenReintentada) {
    imagenReintentada = true;
    const separador = imagenEscena.src.includes("?") ? "&" : "?";
    setTimeout(() => {
      imagenEscena.src = `${imagenEscena.src}${separador}retry=${Date.now()}`;
    }, 1200);
  } else {
    imagenEscena.hidden = true;
    imagenEscena.removeAttribute("src");
  }
});
const narracionEl = document.getElementById("narracion");
const dialogosEl = document.getElementById("dialogos");
const mensajeEfectoEl = document.getElementById("mensaje-efecto");
const panelEstadoEl = document.getElementById("panel-estado");
const bloqueFinal = document.getElementById("bloque-final");
const etiquetaFinal = document.getElementById("etiqueta-final");
const bloqueEstadisticas = document.getElementById("bloque-estadisticas");
const listaEstadisticas = document.getElementById("lista-estadisticas");
const estadisticasHitosTitulo = document.getElementById("estadisticas-hitos-titulo");
const listaHitos = document.getElementById("lista-hitos");
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
  solitario: "🚪 FIN — SOBREVIVISTE, SOLO",
  condenado: "🚔 FIN — TE DICTARON LA PRISIÓN PREVENTIVA",
  represion_derrota: "🪧 FIN — REPRIMIERON EL PIQUETE",
  muerte_manifestacion: "🚑 FIN — NO SOBREVIVISTE (te agarró en la calle)",
  cartonero: "🛒 FIN — TERMINASTE DE CARTONERO",
  referente_piquetero: "✊ FIN — TE CONVERTISTE EN REFERENTE PIQUETERO",
  presidente: "🎖️  FIN — TERMINASTE SIENDO PRESIDENTE",
  perdido: "💊 FIN — TE PERDISTE EN EL CONSUMO",
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
  pantallaModo.hidden = true;
  pantallaAlta.hidden = true;
  pantallaJuego.hidden = false;
}

function mostrarPantallaAlta() {
  pantallaModo.hidden = true;
  pantallaJuego.hidden = true;
  pantallaAlta.hidden = false;
}

async function mostrarPantallaModo() {
  pantallaJuego.hidden = true;
  pantallaAlta.hidden = true;
  pantallaModo.hidden = false;

  btnModoLibre.disabled = true;
  modoLibreNoDisponible.hidden = true;
  try {
    const datos = await apiGet("/api/modo_disponible");
    if (datos.libre_disponible) {
      btnModoLibre.disabled = false;
    } else {
      modoLibreNoDisponible.hidden = false;
    }
  } catch (err) {
    modoLibreNoDisponible.hidden = false;
  }
}

btnModoHistoria.addEventListener("click", () => {
  modoElegido = "historia";
  mostrarPantallaAlta();
});

btnModoLibre.addEventListener("click", () => {
  if (btnModoLibre.disabled) return;
  modoElegido = "libre";
  mostrarPantallaAlta();
});

// --- Cutscene de apertura ---------------------------------------------
// Tiene que coincidir con var(--duracion-intro) de static/style.css.
const DURACION_INTRO_MS = 5500;
let introTimeoutId = null;

function prefiereMovimientoReducido() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function detenerMusicaIntro() {
  introMusica.pause();
  introMusica.currentTime = 0;
  btnActivarSonido.hidden = true;
}

// Los navegadores bloquean el autoplay con sonido si la página no tuvo
// ninguna interacción del usuario todavía (la cutscene arranca sola al
// cargar). Si el bloqueo pasa, mostramos un botón para que lo active con un
// solo click; si directamente no hay archivo de audio puesto en
// static/audio/intro-musica.mp3, el intento falla igual pero en silencio,
// sin romper nada (la cutscene funciona perfecto sin música).
function intentarMusicaIntro() {
  introMusica.volume = 0.55;
  introMusica.currentTime = 0;
  const promesa = introMusica.play();
  if (promesa && typeof promesa.catch === "function") {
    promesa.catch(() => {
      btnActivarSonido.hidden = false;
    });
  }
}

btnActivarSonido.addEventListener("click", () => {
  introMusica.play().catch(() => {});
  btnActivarSonido.hidden = true;
});

function finalizarIntro() {
  if (introTimeoutId) {
    clearTimeout(introTimeoutId);
    introTimeoutId = null;
  }
  detenerMusicaIntro();
  sessionStorage.setItem("introVista", "1");
  pantallaIntro.classList.remove("intro-reproduciendo");
  pantallaIntro.hidden = true;
  mostrarPantallaModo();
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
    mostrarPantallaModo();
    return;
  }

  pantallaIntro.hidden = false;
  introCargando.hidden = false;

  let frames;
  try {
    frames = await apiGet("/api/intro");
  } catch (err) {
    pantallaIntro.hidden = true;
    mostrarPantallaModo();
    return;
  }

  // Cada imagen puede tardar varios segundos en generarse y se piden de a
  // una (ver precargarSecuencial). Si tarda demasiado o falla, saltamos
  // directo al menú en vez de dejar al jugador esperando indefinidamente.
  try {
    await esperarConTimeout(
      precargarSecuencial([frames.calle, frames.helicoptero]),
      45000,
    );
  } catch (err) {
    pantallaIntro.hidden = true;
    introCargando.hidden = true;
    mostrarPantallaModo();
    return;
  }

  introCapaCalle.style.backgroundImage = `url("${frames.calle}")`;
  introCapaHelicoptero.style.backgroundImage = `url("${frames.helicoptero}")`;
  introCargando.hidden = true;

  // Forzar reflow para que el navegador registre el estado inicial antes de
  // agregar la clase que dispara las animaciones (si no, a veces no arrancan).
  void pantallaIntro.offsetWidth;
  pantallaIntro.classList.add("intro-reproduciendo");
  intentarMusicaIntro();
  introTimeoutId = setTimeout(finalizarIntro, DURACION_INTRO_MS);
}

btnSaltarIntro.addEventListener("click", finalizarIntro);

function renderVista(vista) {
  errorAccion.hidden = true;

  if (vista.imagen_url) {
    imagenReintentada = false;
    imagenEscena.src = vista.imagen_url;
    imagenEscena.hidden = false;
  } else {
    imagenEscena.hidden = true;
    imagenEscena.removeAttribute("src");
  }

  tipearTexto(narracionEl, vista.narracion || "");

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
    `🗓️  ${panel.dia || ""}\n` +
    `🎯 Misión: ${panel.mision || ""}\n` +
    `📍 Ubicación: ${panel.ubicacion}\n` +
    `🎒 Inventario/Recursos: ${panel.inventario}\n` +
    `⚠️  Estado/Salud: ${panel.salud}\n` +
    `${linea}`;

  if (vista.es_final) {
    bloqueOpciones.hidden = true;
    bloqueFinal.hidden = false;
    etiquetaFinal.textContent = ETIQUETAS_FINAL[vista.final_tipo] || "FIN DE LA PARTIDA";
    mostrarEstadisticas(vista.estadisticas);
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

function mostrarEstadisticas(stats) {
  if (!stats) {
    bloqueEstadisticas.hidden = true;
    return;
  }
  bloqueEstadisticas.hidden = false;
  listaEstadisticas.innerHTML = "";
  const filas = [
    `🏆 Puntaje final: ${stats.puntaje}`,
    `🗓️ Llegaste a: ${stats.dia}`,
    `🧭 Camino recorrido: ${stats.camino} (alineación ${stats.alineacion >= 0 ? "+" : ""}${stats.alineacion})`,
    `🤝 Reputación barrial final: ${stats.reputacion}`,
    `💰 Terminaste con: ${stats.dinero_final}`,
    `🚶 Lugares distintos recorridos: ${stats.lugares_recorridos}`,
    `⏱️ Turnos jugados: ${stats.turnos}`,
  ];
  filas.forEach((texto) => {
    const li = document.createElement("li");
    li.textContent = texto;
    listaEstadisticas.appendChild(li);
  });

  listaHitos.innerHTML = "";
  if (stats.hitos && stats.hitos.length) {
    estadisticasHitosTitulo.hidden = false;
    stats.hitos.forEach((texto) => {
      const li = document.createElement("li");
      li.textContent = `• ${texto}`;
      listaHitos.appendChild(li);
    });
  } else {
    estadisticasHitosTitulo.hidden = true;
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
    modo: modoElegido,
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

// "Nueva partida" es un reset total, como en cualquier videojuego: se borra
// el estado del servidor y todo lo guardado en esta pestaña (incluido que
// ya viste la intro), y se recarga la página para volver literalmente a la
// pantalla de arranque con la cutscene animada.
async function reiniciarPartidaCompleta() {
  try {
    await apiPost("/api/reiniciar", {});
  } catch (err) {
    // Si falla el POST igual recargamos: la sesión vieja va a quedar
    // colgada en el servidor, pero el jugador no se queda trabado acá.
  }
  sessionStorage.clear();
  window.location.reload();
}

btnJugarDeNuevo.addEventListener("click", reiniciarPartidaCompleta);

btnReiniciar.addEventListener("click", () => {
  if (!confirm("¿Seguro que querés abandonar esta partida y empezar de nuevo?")) return;
  reiniciarPartidaCompleta();
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
