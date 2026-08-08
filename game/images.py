"""Construcción de URLs de imagen contra la API pública de Pollinations.ai.

Se usa únicamente en los nodos "climáticos" de la historia (definidos en
game/story.py mediante el campo `imagen_en`) y en la cutscene de apertura,
nunca en cada turno.

Historial del estilo (para quien toque esto después): la primera versión
nombraba juegos puntuales ("Leisure Suit Larry", "King's Quest") para pedir
pixel art retro. Probado en la práctica, esos nombres propios dominan tanto
la composición que Pollinations devuelve escenas genéricas de fantasía sin
relación con lo pedido (un personaje al lado de una puerta, un paisaje de
otro planeta) sin importar la escena que se describa — validado con varias
seeds y descripciones distintas. El estilo actual describe género y ánimo
en vez de títulos puntuales, evita instrucciones de "texto/HUD en pantalla"
(el modelo no puede renderizar texto real y termina dibujando un logo
ilegible) y agrega una directiva explícita para que no genere contenido
sexualizado.
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
    "realistic proportions, no on-screen text, no logos, no HUD, no subtitles, "
    "fully clothed people in ordinary early-2000s Argentine street clothing, "
    "non-sexualized, respectful serious documentary tone"
)

BASE_URL = "https://image.pollinations.ai/prompt/"


def construir_prompt(escena_en_ingles: str) -> str:
    """Arma el prompt final respetando exactamente el estilo pedido."""
    escena = escena_en_ingles.strip().rstrip(".")
    return f"{ESTILO_PREFIJO}, {escena}, {ESTILO_SUFIJO}"


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
