"""Intérprete de acciones libres (opción 4: "escribí lo que quieras").

No usa ningún LLM: clasifica el texto del jugador por palabras clave en
categorías amplias y devuelve un `Resolucion` con narración de reemplazo
(estilo rioplatense) y efectos mecánicos. `game/llm.py` puede después
reemplazar únicamente el texto narrado, sin tocar los efectos ya calculados
acá — así el juego funciona igual de bien con o sin API key configurada.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Tuple

from game.state import EstadoJugador


@dataclass
class Resolucion:
    narracion: str
    salud_delta: int = 0
    reputacion_delta: int = 0
    dinero_delta: Dict[str, int] = field(default_factory=dict)
    flags_add: Tuple[str, ...] = ()
    estados_add: Tuple[str, ...] = ()


CATEGORIAS: Dict[str, Tuple[str, ...]] = {
    "violencia": (
        "pegar", "pelear", "atacar", "robar", "afanar", "garcar", "empujar",
        "cagar a trompadas", "romper", "tirar piedra", "agredir",
    ),
    "huida": (
        "correr", "huir", "escapar", "esconderse", "rajar", "irme corriendo",
        "meterme en", "salir corriendo", "borrarme",
    ),
    "ayuda": (
        "ayudar", "compartir", "dar", "colaborar", "curar", "socorrer",
        "levantar a", "proteger", "defender a",
    ),
    "negociacion": (
        "hablar", "negociar", "preguntar", "pedir", "convencer", "charlar",
        "explicar", "pactar", "ofrecer",
    ),
    "busqueda": (
        "buscar", "investigar", "revisar", "mirar", "observar", "escuchar",
        "fijarme", "rastrear",
    ),
    "descanso": (
        "descansar", "dormir", "sentarme", "tomar aire", "parar un rato",
        "recuperar aliento",
    ),
}


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _clasificar(texto_normalizado: str) -> str:
    for categoria, palabras in CATEGORIAS.items():
        for palabra in palabras:
            if _normalizar(palabra) in texto_normalizado:
                return categoria
    return "generico"


_FRASES_RIOPLATENSES = (
    "che", "boludo", "posta", "ni en pedo", "ameo", "un quilombo",
    "de una", "zafaste", "la vas viendo",
)


def interpretar_accion_libre(estado: EstadoJugador, texto_jugador: str) -> Resolucion:
    """Devuelve narración + efectos mecánicos para una acción de texto libre."""

    texto_normalizado = _normalizar(texto_jugador)
    categoria = _clasificar(texto_normalizado)

    if categoria == "violencia":
        if random.random() < 0.5:
            return Resolucion(
                narracion=(
                    f'Te tirás de lleno a "{texto_jugador.strip()}". Por un segundo funciona, pero enseguida '
                    "se te viene la bronca de varios encima. Salís del entrevero con lo puesto y el corazón "
                    "en la garganta, che."
                ),
                salud_delta=random.randint(-25, -10),
                reputacion_delta=-8,
            )
        return Resolucion(
            narracion=(
                f'Vas con todo: "{texto_jugador.strip()}". Sorprendentemente te sale bien y conseguís '
                "sacar ventaja de la situación, aunque después de esto la gente del barrio te va a mirar distinto."
            ),
            salud_delta=random.randint(-10, -2),
            reputacion_delta=-4,
            dinero_delta={"pesos": random.choice([0, 0, 10])},
        )

    if categoria == "huida":
        return Resolucion(
            narracion=(
                f'Decidís que lo tuyo es "{texto_jugador.strip()}" y le metés pata. El corazón te retumba en '
                "los oídos, pero conseguís poner distancia antes de que la cosa se complique más."
            ),
            salud_delta=random.randint(-8, 0),
        )

    if categoria == "ayuda":
        return Resolucion(
            narracion=(
                f'Sin pensarlo mucho, hacés lo que te sale del pecho: "{texto_jugador.strip()}". No es fácil ni '
                "cómodo, pero alguien se va a acordar de esto. En medio de tanto quilombo, un gesto así pesa."
            ),
            salud_delta=random.randint(-8, -1),
            reputacion_delta=random.randint(4, 9),
        )

    if categoria == "negociacion":
        exito = random.random() < 0.6
        if exito:
            return Resolucion(
                narracion=(
                    f'Probás con calma: "{texto_jugador.strip()}". Por suerte encontrás a alguien dispuesto a '
                    "escuchar, y la charla destrabá algo que a los gritos no se hubiera resuelto nunca."
                ),
                reputacion_delta=3,
            )
        return Resolucion(
            narracion=(
                f'Intentás "{texto_jugador.strip()}", pero nadie está para diálogo hoy. Te contestan cortante, '
                "casi con desprecio, y te quedás con las palabras a medio armar."
            ),
            reputacion_delta=-1,
        )

    if categoria == "busqueda":
        return Resolucion(
            narracion=(
                f'Te tomás un segundo para "{texto_jugador.strip()}". El quilombo alrededor no para, pero '
                "conseguís hacerte una idea más clara de lo que está pasando antes de moverte de nuevo."
            ),
        )

    if categoria == "descanso":
        return Resolucion(
            narracion=(
                f'Te das el gusto de "{texto_jugador.strip()}", aunque sea un momento. El cuerpo te lo venía '
                "pidiendo a gritos."
            ),
            salud_delta=random.randint(3, 10),
        )

    # Categoría genérica: el GM improvisa algo neutro/levemente riesgoso,
    # coherente con el hecho de que en diciembre de 2001 nada sale gratis.
    return Resolucion(
        narracion=(
            f'Intentás algo por tu cuenta: "{texto_jugador.strip()}". No es de las cosas que estaban en el '
            "menú de opciones, y el barrio no perdona improvisadas: sale más o menos, ni para bien ni para mal."
        ),
        salud_delta=random.randint(-6, 2),
    )
