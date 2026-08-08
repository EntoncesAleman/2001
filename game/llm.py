"""Narración opcional de acciones libres vía la API de Anthropic (Claude).

Esto es 100% opcional: si no está instalado el paquete `anthropic` o no hay
`ANTHROPIC_API_KEY` en el entorno, el juego sigue funcionando perfectamente
con el intérprete de palabras clave de `game/free_text.py`. Cuando el LLM
está disponible, se usa únicamente para reescribir el *texto* narrado de una
acción libre — los efectos mecánicos (salud, dinero, reputación) ya fueron
calculados antes y no se tocan, para que el juego nunca dependa de que la
API responda algo "parseable".
"""

from __future__ import annotations

import os
from typing import Optional

SYSTEM_PROMPT = (
    "Sos el Game Master de un RPG textual de supervivencia ambientado en la "
    "crisis socioeconómica de diciembre de 2001 en el Gran Buenos Aires y "
    "CABA, Argentina. Narrás en segunda persona ('estás', 'escuchás'), con "
    "tono cinematográfico, neorrealista, crudo e inmersivo. Usás dialecto "
    "rioplatense auténtico de la época ('che', 'boludo', 'garca', 'ameo', "
    "'chabón') con moderación, sin abusar. Integrás de forma orgánica "
    "elementos como el Corralito, los Patacones y Lecops, los clubes de "
    "trueque, los cacerolazos, las asambleas barriales y los saqueos cuando "
    "corresponda al contexto. Respondé SOLO con 2 a 4 oraciones de "
    "narración, sin listas, sin encabezados, sin repetir el resultado "
    "mecánico que ya te paso (no lo contradigas, simplemente narralo)."
)

MODELO_POR_DEFECTO = "claude-sonnet-5"


def modelo_configurado() -> bool:
    """True si hay todo lo necesario para intentar una llamada real a la API."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def generar_narracion_libre(
    contexto_escena: str,
    ubicacion: str,
    accion_jugador: str,
    resultado_mecanico: str,
) -> Optional[str]:
    """Devuelve una narración generada por Claude, o None si no se puede.

    `resultado_mecanico` es una descripción corta en castellano de lo que ya
    se decidió mecánicamente (p. ej. "pierde 15 de salud, gana reputación
    barrial"), para que el modelo lo narre sin inventar otro desenlace.
    """
    if not modelo_configurado():
        return None

    try:
        import anthropic

        cliente = anthropic.Anthropic()
        mensaje_usuario = (
            f"Escena actual: {contexto_escena}\n"
            f"Ubicación: {ubicacion}\n"
            f'El jugador decide, por su cuenta: "{accion_jugador}"\n'
            f"Resultado mecánico ya definido (narralo, no lo cambies): {resultado_mecanico}"
        )
        respuesta = cliente.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", MODELO_POR_DEFECTO),
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": mensaje_usuario}],
        )
        bloques = [b.text for b in respuesta.content if getattr(b, "type", "") == "text"]
        texto = "\n".join(bloques).strip()
        return texto or None
    except Exception:
        # Cualquier problema de red, autenticación, rate-limit, etc.: el
        # juego sigue con la narración de free_text.py sin explotar.
        return None
