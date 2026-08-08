"""Construcción de URLs de imagen contra la API pública de Pollinations.ai.

Se usa únicamente en los nodos "climáticos" de la historia (definidos en
game/story.py mediante el campo `imagen_en`), nunca en cada turno.
"""

from __future__ import annotations

import random
import urllib.parse

ESTILO_PREFIJO = (
    "1980s-1990s Sierra On-Line style VGA and EGA point-and-click adventure "
    "game screenshot, in the visual style of Leisure Suit Larry, King's Quest "
    "and Space Quest, chunky low-resolution pixel art, visible dithering "
    "gradients, flat saturated color regions, thick dark pixel outlines, "
    "black dialogue text box overlay at the top of the frame with white "
    "pixelated bitmap font, grit, detailed pixelated illustration"
)
ESTILO_SUFIJO = "authentic retro DOS adventure game screenshot, EGA and VGA 256-color palette, pixel art"

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
