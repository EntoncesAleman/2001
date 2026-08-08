# Argentina 2001 — RPG textual

Juego de rol interactivo de supervivencia urbana ambientado en el Gran Buenos
Aires y CABA durante la crisis socioeconómica de diciembre de 2001: el
Corralito, los Patacones y Lecops, los clubes de trueque, las asambleas
barriales, los cacerolazos y los saqueos.

El mismo motor de juego (`game/`) tiene **dos frontends**:

- **Terminal** (`main.py`): con [rich](https://github.com/Textualize/rich) para una interfaz de consola prolija.
- **Web** (`api/index.py`): una app [Flask](https://flask.palletsprojects.com/) lista para desplegar en [Vercel](https://vercel.com/).

En los momentos climáticos de la historia, el juego genera un link de imagen
en **pixel art retro 16-bit** usando la API pública de
[Pollinations.ai](https://pollinations.ai/) (en la terminal se imprime el
link; en la web se muestra como imagen real).

---

## 1. Instalación

Requiere **Python 3.9 o superior**.

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` instala:

- `rich` — interfaz de consola (colores, paneles, prompts).
- `requests` — llamadas HTTP (usado si activás la descarga de imágenes, ver más abajo).
- `Flask` — el servidor web para la variante navegador/Vercel.
- `anthropic` / `google-genai` — opcionales, solo se usan si configurás
  `ANTHROPIC_API_KEY` o `GEMINI_API_KEY` respectivamente (ver sección 4).

No es obligatorio instalar ninguno de los dos ni tener API key: **el juego funciona
completo sin ninguna clave**, con un motor narrativo de nodos con estado
propio y un intérprete de texto libre por palabras clave.

---

## 2. Jugar en la terminal

```bash
python3 main.py
```

- Al arrancar te pide **nombre, trasfondo, barrio de partida y objetivo**
  (podés escribir lo que quieras, no hace falta usar los ejemplos).
- Cada turno te muestra la narración, diálogos en rioplatense de época, un
  panel de estado (ubicación / inventario y plata / salud) y **3 opciones
  numeradas + la posibilidad de escribir cualquier acción libre**.
- Comandos especiales en cualquier momento: escribí `guardar` para guardar la
  partida (`partidas/partida.json`) o `salir` para terminar.
- Si volvés a ejecutar `python3 main.py` y existe una partida guardada, te
  pregunta si querés continuarla.
- Cuando el juego imprime un link `https://image.pollinations.ai/...`, pegalo
  en el navegador para ver la ilustración pixel art de esa escena.

---

## 3. Jugar en el navegador (local)

```bash
python3 api/index.py
```

Abrí `http://localhost:5000` en el navegador. Es la misma historia y el
mismo motor que la terminal, pero con las imágenes mostrándose directamente
en pantalla y opciones como botones.

El estado de la partida se guarda en una **cookie de sesión firmada** de
Flask (no hay base de datos): cada navegador/sesión tiene su propia partida.

Para producción, seteá una clave propia en vez de la que trae por defecto:

```bash
export SECRET_KEY="una-clave-larga-y-random-tuya"
```

---

## 4. (Opcional) Narración enriquecida con un LLM

El intérprete de acciones libres (`game/free_text.py`) ya resuelve
mecánicamente cualquier texto que escriba el jugador (efectos en salud,
dinero, reputación, etc.) con narración propia en rioplatense. Si además
configurás una API key de **Anthropic (Claude)** o de **Google (Gemini)**,
esa narración se reemplaza por una generada por el modelo — los efectos
mecánicos **no cambian**, solo mejora el texto. Elegí uno de los dos:

```bash
# Opción A: Claude
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-5"   # opcional, es el default

# Opción B: Gemini
export GEMINI_API_KEY="AIza..."             # la sacás de https://aistudio.google.com/apikey
export GEMINI_MODEL="gemini-2.5-flash"      # opcional, es el default
```

Si tenés las dos keys configuradas a la vez, se usa Anthropic por defecto;
podés forzar cuál usar con `export LLM_PROVIDER="gemini"` (o `"anthropic"`).

Si no configurás nada, o falla la llamada por cualquier motivo (sin
conexión, rate limit, key inválida, etc.), el juego sigue funcionando con
la narración local sin ningún error visible para el jugador.

---

## 5. Desplegar la versión web en Vercel

El repo ya incluye `vercel.json` apuntando a `api/index.py` (Flask) vía
`@vercel/python`, con los archivos de `static/` servidos directamente.

```bash
npm i -g vercel     # si no lo tenés instalado
vercel login
vercel               # deploy de preview
vercel --prod        # deploy de producción
```

Después de vincular el proyecto, seteá la variable de entorno `SECRET_KEY`
(y opcionalmente `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` o `GEMINI_API_KEY` /
`GEMINI_MODEL`, ver sección 4) desde el dashboard de Vercel o con:

```bash
vercel env add SECRET_KEY production
```

---

## 6. Arquitectura del proyecto

```
juego texto/
├── main.py                  # Frontend de terminal (rich)
├── api/
│   └── index.py              # Frontend web (Flask) — mismo motor, para Vercel
├── templates/
│   └── index.html            # Página del juego (estética CRT/pixel art)
├── static/
│   ├── style.css              # Tema visual retro 16-bit
│   └── game.js                 # Lógica del cliente (fetch a /api/*)
├── game/                      # Motor del juego — sin I/O de terminal ni red directa
│   ├── state.py                # EstadoJugador, Dinero (pesos/Patacones/Lecops/créditos)
│   ├── story.py                 # Grafo de nodos narrativos + opciones + finales
│   ├── free_text.py              # Intérprete de acciones libres por palabras clave
│   ├── llm.py                     # Narración opcional vía API de Anthropic
│   ├── images.py                   # Constructor de URLs de Pollinations.ai
│   └── engine.py                    # Conecta todo: crear partida, avanzar turnos
├── partidas/                  # Partidas guardadas en JSON (terminal)
├── requirements.txt
├── vercel.json
└── README.md
```

`main.py` y `api/index.py` **nunca duplican lógica de juego**: los dos
llaman a las mismas funciones de `game/engine.py`
(`crear_estado`, `vista_actual`, `elegir_opcion`, `accion_libre`,
`guardar_estado`, `cargar_estado`). Cambiar una regla del juego (por ejemplo,
cuánta salud quita un cacerolazo) se hace una sola vez, en `game/story.py`,
y se refleja automáticamente en ambos frontends.

### Mecánica de riesgo ("no hay armadura de guion")

Cada opción de `game/story.py` puede tener un rango aleatorio de salud
(`salud_delta`) y, en algunos nodos, un destino alternativo con probabilidad
propia (`destino_alt` / `prob_alt`) — por ejemplo, intentar sobornar al
guardia del banco puede salir bien o mal. Si la salud llega a 0, el jugador
muere en el acto (`final_muerte`), sin importar en qué nodo esté.

### Finales

Al final de la historia (`game/engine.py:elegir_final`) el desenlace depende
de las flags y la reputación barrial acumuladas durante la partida:
`final_objetivo_cumplido`, `final_comunidad`, `final_huida`,
`final_solitario` o `final_muerte`.
