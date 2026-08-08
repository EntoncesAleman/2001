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


# ---------------------------------------------------------------------------
# Estilo alternativo para la cutscene de apertura.
#
# ESTILO_PREFIJO (arriba) nombra títulos puntuales ("Leisure Suit Larry",
# "King's Quest", "Space Quest"): probado empíricamente, esas referencias
# dominan tanto la composición que Pollinations devuelve casi siempre la
# misma escena genérica de personaje-parado-frente-a-una-puerta sin importar
# qué se pida (validado con múltiples seeds y descripciones). Para escenas
# muy específicas como la del disturbio/Casa Rosada de la intro, conviene un
# estilo igual de "pixel art retro" pero descrito por género en vez de por
# título, que sí sigue el contenido pedido.
# ---------------------------------------------------------------------------

ESTILO_CUTSCENE_PREFIJO = (
    "cinematic 16-bit pixel art video game screenshot, dithering, limited retro "
    "color palette, dramatic lighting, detailed pixel art illustration"
)
ESTILO_CUTSCENE_SUFIJO = "retro pixel art video game cutscene"


def build_pollinations_url_cinematica(
    escena_en_ingles: str,
    ancho: int = 800,
    alto: int = 400,
    seed: int | None = None,
) -> str:
    """Como build_pollinations_url, pero con el estilo alternativo de arriba."""
    if seed is None:
        seed = random.randint(1, 999_999)

    escena = escena_en_ingles.strip().rstrip(".")
    prompt = f"{ESTILO_CUTSCENE_PREFIJO}, {escena}, {ESTILO_CUTSCENE_SUFIJO}"
    prompt_codificado = urllib.parse.quote(prompt, safe="")

    return (
        f"{BASE_URL}{prompt_codificado}"
        f"?width={ancho}&height={alto}&nologo=true&seed={seed}"
    )
