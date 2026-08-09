"""Construcción de URLs de imagen contra la API pública de Pollinations.ai.

Se usa únicamente en los nodos "climáticos" de la historia (definidos en
game/story.py mediante el campo `imagen_en`) y en la cutscene de apertura,
nunca en cada turno.

Historial del estilo (para quien toque esto después):
- v1 nombraba juegos puntuales ("Leisure Suit Larry", "King's Quest") para
  pedir pixel art retro. Esos nombres propios dominaban tanto la composición
  que Pollinations devolvía escenas genéricas de fantasía sin relación con lo
  pedido, sin importar la escena — descartado.
- v2 (género en vez de títulos, sin pedir "texto/HUD en pantalla" porque el
  modelo dibuja un logo ilegible) funcionó bien de contenido pero tendía a
  salir con calles vacías, sin gente, y a veces con arquitectura que no se
  parece en nada a Buenos Aires (se probó pedir "pixel art estilo VGA de
  aventura gráfica" para darle más onda de videojuego retro, y el resultado
  fue directamente peor: un vehículo futurista y montañas en el horizonte
  — Buenos Aires no tiene montañas — o sea que el género "aventura gráfica"
  hijackea la composición tanto como los títulos puntuales de v1).
- v3 (actual): mantiene el estilo "digital painting" fotoperiodístico de v2
  (es el que mejor mantiene el contenido pedido) pero reordena el prompt para
  que la ESCENA vaya primero (más peso en la composición) y agrega, como
  bloque de contenido aparte al final, anclas explícitas de fidelidad: "Buenos
  Aires, sin montañas", gente presente siempre (nunca una escena vacía/
  desierta), ropa de verano (diciembre en Argentina es verano, no invierno).
  Validado bajado y mirando las imágenes reales para calle/helicóptero/tren de
  cartoneros antes de aplicar esto a todo el juego.
"""

from __future__ import annotations

import random
import urllib.parse

ESTILO_PREFIJO = (
    "gritty realistic cinematic digital painting, moody atmospheric lighting, "
    "muted dusk color palette of deep blues, purples and warm oranges, highly "
    "detailed illustration, documentary photojournalism framing"
)
ESTILO_SUFIJO = (
    "set in Buenos Aires, Argentina, a flat South American city with no "
    "mountains or hills, low-rise early-1900s buildings, corner shops with "
    "awnings, wrought-iron balconies and period-correct Argentine cars, "
    "populated with ordinary Argentine people going about their day (never an "
    "empty or deserted scene), people dressed for a hot southern-hemisphere "
    "summer night (short sleeves, light clothing, no heavy coats), realistic "
    "proportions, no on-screen text, no logos, no HUD, no subtitles, fully "
    "clothed people, non-sexualized, respectful serious documentary tone"
)

BASE_URL = "https://image.pollinations.ai/prompt/"


def construir_prompt(escena_en_ingles: str) -> str:
    """Arma el prompt final respetando exactamente el estilo pedido.

    La escena va primero (así el modelo le da más peso al contenido pedido:
    el edificio, la gente, el helicóptero) y el estilo/las anclas de fidelidad
    van después, como contexto adicional en vez de dominar la composición.
    """
    escena = escena_en_ingles.strip().rstrip(".")
    return f"{escena}, {ESTILO_PREFIJO}, {ESTILO_SUFIJO}"


def build_pollinations_url(
    escena_en_ingles: str,
    ancho: int = 800,
    alto: int = 400,
    seed: int | None = None,
) -> str:
    """Construye la URL de imagen de Pollinations.ai.

    `escena_en_ingles` debe ser la descripción de la escena y los personajes,
    ya en inglés (el resto del prompt/estilo se agrega automáticamente).
    """
    if seed is None:
        seed = random.randint(1, 999_999)

    prompt = construir_prompt(escena_en_ingles)
    # safe="" fuerza a codificar también "/" u otros caracteres que Pollinations
    # interpretaría como parte del path en vez de como texto del prompt.
    prompt_codificado = urllib.parse.quote(prompt, safe="")

    return (
        f"{BASE_URL}{prompt_codificado}"
        f"?width={ancho}&height={alto}&nologo=true&seed={seed}"
    )


def markdown_de_imagen(escena_en_ingles: str, alt_texto: str = "Escena", **kwargs) -> str:
    """Devuelve la línea Markdown lista para imprimir/mostrar."""
    url = build_pollinations_url(escena_en_ingles, **kwargs)
    return f"![{alt_texto}]({url})"
