# 2001: Odisea en Buenos Aires — RPG textual

Juego de rol interactivo de supervivencia urbana ambientado en el Gran Buenos
Aires y CABA durante la crisis socioeconómica de diciembre de 2001: el
Corralito, los Patacones y Lecops, los clubes de trueque, las asambleas
barriales, los cacerolazos y los saqueos.

El mismo motor de juego (`game/`) tiene **dos frontends**:

- **Terminal** (`main.py`): con [rich](https://github.com/Textualize/rich) para una interfaz de consola prolija, con efecto de tipeo tipo máquina de escribir.
- **Web** (`api/index.py`): una app [Flask](https://flask.palletsprojects.com/) lista para desplegar en [Vercel](https://vercel.com/), con cutscene animada de apertura y el mismo efecto de tipeo (con clic sintetizado, sin ningún sample de audio real).

Al arrancar, elegís entre dos formas de jugar:

- **Modo historia** — un grafo de ~40 escenas ya escritas (`game/story.py`), con
  economía (comprar/vender, mercado negro de objetos robados, comida que cura,
  hospital), una sidequest en el comedor del barrio, eventos aleatorios en el
  camino (robos, quedar atrapado en una manifestación), persecuciones
  policiales, una cárcel interactiva (abogado, coima, audiencia) y 7 finales
  distintos. Funciona 100% sin ninguna API.
- **Modo libre (IA)** — sin grafo fijo: un LLM (Gemini o Claude) improvisa
  toda la historia turno a turno. Solo se ofrece si el servidor tiene una API
  key configurada (ver sección 4).

En los momentos climáticos de la historia, el juego genera un link de imagen
en estilo **pintura cinematográfica realista** (paleta azul/violeta, tono
documental) usando la API pública de [Pollinations.ai](https://pollinations.ai/)
(en la terminal se imprime el link; en la web se muestra como imagen real,
y también hay una cutscene animada de apertura).

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
  en el navegador para ver la ilustración de esa escena.

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

## 4. (Opcional pero recomendado) Gemini como Game Master

En **modo historia**, el motor de nodos (`game/story.py` + `game/free_text.py`)
resuelve **todo** mecánicamente por su cuenta (salud, dinero, reputación, a
qué escena se pasa) y trae narración propia en rioplatense escrita a mano —
así el juego es 100% jugable sin ninguna API key. Pero si configurás
**Google Gemini** (o Anthropic/Claude), ese texto fijo pasa a ser el último
recurso: el LLM se convierte en el narrador principal de cada turno — tanto
para las opciones numeradas como para las acciones libres — redactando la
escena en su propio estilo a partir del resultado que el motor ya decidió.
Los efectos mecánicos **nunca** los define ni puede cambiarlos el LLM, solo
la prosa que lee el jugador.

La misma API key habilita además el **modo libre** (`game/modo_libre.py`):
ahí no hay grafo fijo, el LLM decide la escena, las opciones tácticas y los
efectos de cada turno directamente (siempre en JSON estructurado, que el
motor valida y limita antes de aplicar — por ejemplo, ningún turno puede
curar más de 30 de salud ni matar más rápido que perdiendo 60). Si no hay
ninguna key configurada, el modo libre directamente no aparece como opción.

Elegí uno de los dos proveedores (si configurás las dos, gana Gemini):

```bash
# Opción A: Claude
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-5"   # opcional, es el default

# Opción B: Gemini
export GEMINI_API_KEY="AIza..."             # la sacás de https://aistudio.google.com/apikey
export GEMINI_MODEL="gemini-2.5-flash"      # opcional, es el default
```

Si tenés las dos keys configuradas a la vez, se usa Gemini por defecto;
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
│   └── index.html            # Página del juego (estética CRT + cutscene animada)
├── static/
│   ├── style.css              # Tema visual + animación de la cutscene
│   ├── game.js                 # Lógica del cliente (fetch a /api/*)
│   └── audio/
│       └── intro-musica.mp3     # (opcional) música de fondo de la cutscene, la ponés vos
├── game/                      # Motor del juego — sin I/O de terminal ni red directa
│   ├── state.py                # EstadoJugador, Dinero (pesos/Patacones/Lecops/créditos)
│   ├── story.py                 # Grafo de nodos narrativos + opciones + finales (modo historia)
│   ├── free_text.py              # Intérprete de acciones libres por palabras clave
│   ├── llm.py                     # Narración (modo historia) y turnos en JSON (modo libre)
│   ├── images.py                   # Constructor de URLs de Pollinations.ai
│   ├── engine.py                    # Motor del modo historia: crear partida, avanzar turnos
│   └── modo_libre.py                 # Motor del modo libre: sin grafo, todo lo decide el LLM
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

Siete desenlaces posibles:

- `objetivo_cumplido`, `comunidad` o `solitario` — se deciden en
  `game/engine.py:elegir_final` según las flags y la reputación barrial
  acumuladas al llegar al hub nocturno (`calle_noche`).
- `muerte` — la salud llegó a 0 en cualquier momento de la partida.
- `represion_derrota` — te reprimen el piquete en el que estabas.
- `condenado` — caer preso (saqueando, en una persecución, o intentando
  colarte en un control de ruta) no termina la partida: en `carcel` /
  `carcel_audiencia` podés pagar un abogado, coimear, o jugártela sin más.
  Si no te sale nada, este es el final real.
- `presidente` — el final "secreto": infiltrarte en la Casa Rosada, que
  queda desprotegida tras la partida del helicóptero presidencial (el
  mismo de la cutscene de apertura), y sentarte en el sillón.

No hay forma de terminar la partida saliendo del Conurbano/CABA: cualquier
intento de cruzar el límite del AMBA (`control_ruta`) siempre te devuelve
—en el mejor caso con un buen susto, en el peor, preso.

### Economía, misiones y eventos aleatorios (modo historia)

- **Comida cura salud**: conseguís "bolsa de mercadería" en el trueque, el
  comedor o saqueando, y la "comés" en cualquier momento desde la esquina
  del barrio.
- **Hospital**: consulta privada rápida (cuesta pesos, cura mucho) o guardia
  pública gratis (cura menos).
- **Mercado negro**: el único lugar donde vender objetos robados (el
  televisor, el cuadro afanado de la Casa Rosada) — turbio y difícil de
  llegar (`club_trueque` → `camino_mercado_negro`, con riesgo de asalto en
  el camino).
- **Sidequest del comedor**: Doña Rosa te pide un encargo perdido; lo
  encontrás revisando en el cibercafé o en el supermercado saqueado, y
  volvés a entregárselo por una recompensa.
- **Eventos aleatorios**: cada vez que volvés a la esquina del barrio hay
  una chance chica de que te asalten o quedes atrapado en una
  manifestación que no era la tuya — nunca en el primer turno, nunca dos
  veces seguidas.
