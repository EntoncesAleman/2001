"""Narración de cada turno vía un LLM externo (Gemini o Claude), con el motor
de nodos propio (game/story.py + game/free_text.py) como último recurso.

Gemini (o Claude) es el narrador principal: cuando hay una API key
configurada, se le pide que redacte el texto que lee el jugador — tanto para
las opciones numeradas como para las acciones libres. Los efectos mecánicos
(salud, dinero, reputación, a qué nodo se pasa) los decide siempre el motor
de juego ANTES de llamar al LLM y nunca cambian según lo que responda: el
LLM solo dramatiza un resultado ya definido, nunca lo inventa. Si no hay
ninguna key configurada, o falla la llamada por cualquier motivo (sin
conexión, rate limit, key inválida), se usa el texto fijo de game/story.py
(o el de game/free_text.py para acciones libres) — esa es la razón de ser
del motor de nodos: garantizar que el juego sea 100% jugable sin ninguna
API, no reemplazar al LLM cuando sí está disponible.

Proveedor usado (auto-detectado por qué variable de entorno esté seteada,
priorizando Gemini si tenés las dos, o forzado con LLM_PROVIDER=gemini|anthropic):

- Google Gemini:      GEMINI_API_KEY    [+ GEMINI_MODEL opcional]
- Anthropic (Claude): ANTHROPIC_API_KEY [+ ANTHROPIC_MODEL opcional]
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

MODELO_ANTHROPIC_POR_DEFECTO = "claude-sonnet-5"
MODELO_GEMINI_POR_DEFECTO = "gemini-2.5-flash"


def _proveedor_activo() -> Optional[str]:
    """Decide qué proveedor usar según las variables de entorno presentes."""
    forzado = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if forzado in ("anthropic", "claude"):
        return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else None
    if forzado in ("gemini", "google"):
        return "gemini" if os.environ.get("GEMINI_API_KEY") else None

    # Sin forzar nada: el que tenga la key seteada, priorizando Gemini si
    # por algún motivo estuvieran las dos.
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def modelo_configurado() -> bool:
    """True si hay todo lo necesario para intentar una llamada real a la API."""
    proveedor = _proveedor_activo()
    if proveedor == "anthropic":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True
    if proveedor == "gemini":
        try:
            from google import genai  # noqa: F401
        except ImportError:
            return False
        return True
    return False


def _mensaje_usuario(contexto_escena: str, ubicacion: str, accion_jugador: str, resultado_mecanico: str) -> str:
    return (
        f"Escena actual: {contexto_escena}\n"
        f"Ubicación: {ubicacion}\n"
        f'El jugador decide, por su cuenta: "{accion_jugador}"\n'
        f"Resultado mecánico ya definido (narralo, no lo cambies): {resultado_mecanico}"
    )


def _generar_con_anthropic(mensaje_usuario: str) -> Optional[str]:
    import anthropic

    cliente = anthropic.Anthropic()
    respuesta = cliente.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", MODELO_ANTHROPIC_POR_DEFECTO),
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": mensaje_usuario}],
    )
    bloques = [b.text for b in respuesta.content if getattr(b, "type", "") == "text"]
    texto = "\n".join(bloques).strip()
    return texto or None


def _generar_con_gemini(mensaje_usuario: str) -> Optional[str]:
    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    respuesta = cliente.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", MODELO_GEMINI_POR_DEFECTO),
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=300,
        ),
    )
    texto = (getattr(respuesta, "text", None) or "").strip()
    return texto or None


def generar_narracion(
    contexto_escena: str,
    ubicacion: str,
    accion_jugador: str,
    resultado_mecanico: str,
) -> Optional[str]:
    """Devuelve una narración generada por el LLM activo, o None si no se puede.

    Sirve tanto para acciones libres como para opciones numeradas: en ambos
    casos el motor de juego ya decidió los efectos y el nodo/destino antes de
    llamar acá. `resultado_mecanico` describe en castellano ese resultado ya
    fijado (p. ej. "pasa a la fila del banco" o "pierde 15 de salud, gana
    reputación barrial, avanza a la represión"), para que el modelo lo narre
    en su propio estilo sin inventar un desenlace distinto.
    """
    proveedor = _proveedor_activo()
    if proveedor is None or not modelo_configurado():
        return None

    mensaje = _mensaje_usuario(contexto_escena, ubicacion, accion_jugador, resultado_mecanico)

    try:
        if proveedor == "anthropic":
            return _generar_con_anthropic(mensaje)
        if proveedor == "gemini":
            return _generar_con_gemini(mensaje)
    except Exception:
        # Cualquier problema de red, autenticación, rate-limit, etc.: el
        # juego sigue con la narración de free_text.py sin explotar.
        return None
    return None
