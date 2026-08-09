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

import json
import os
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Modo libre: acá el LLM no solo narra, decide toda la historia turno a
# turno (game/modo_libre.py). Por eso necesita responder en un JSON
# estructurado que el motor pueda parsear, en vez de una narración libre.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_LIBRE = (
    "Sos el Game Master de un RPG textual de supervivencia ambientado en la "
    "crisis socioeconómica de diciembre de 2001 en el Gran Buenos Aires y "
    "CABA, Argentina. Esto es el 'modo libre': no hay texto fijo, vos "
    "redactás cada escena con tus propias palabras y generás vos las "
    "imágenes según la situación — pero la AVENTURA EN SÍ (los hitos que "
    "pasan, los caminos posibles, los finales a los que se puede llegar) "
    "tiene que ser LA MISMA que la del modo con guion fijo del juego. No "
    "estás inventando una historia nueva: estás disfrazando con tu propio "
    "estilo, y con imágenes distintas cada vez, una historia que ya tiene "
    "una estructura obligatoria. Nunca te dispersés de ella.\n"
    "\n"
    "ESTRUCTURA OBLIGATORIA (capítulos, en este orden estricto):\n"
    "1. Días previos: el Corralito ya está declarado, tensión creciente. El "
    "personaje puede ir al banco, a una asamblea barrial, a un club de "
    "trueque, al cibercafé — explorando libremente antes de que pase nada "
    "grave.\n"
    "2. Noche del 19 de diciembre: De la Rúa declara el estado de sitio por "
    "cadena nacional; estalla un cacerolazo espontáneo y masivo en todo el "
    "país.\n"
    "3. Día del 20 de diciembre: saqueos a supermercados, una multitud "
    "enorme se junta en Plaza de Mayo, represión policial dura (gases, "
    "postas de goma, caballos), y por la tarde la noticia de la renuncia de "
    "De la Rúa con la imagen icónica del helicóptero despegando desde la "
    "Casa Rosada.\n"
    "4-6. La semana de los presidentes: Ramón Puerta interino, después "
    "Adolfo Rodríguez Saá (asume por la Asamblea Legislativa, anuncia el "
    "default de la deuda entre aplausos, dura pocos días), después Eduardo "
    "Duhalde asume el 1° de enero — de fondo, cada vez más gente se sube de "
    "noche al 'tren de los cartoneros' para juntar cartón y sobrevivir.\n"
    "7. Cierre: el personaje decide cómo sigue su vida con lo que le quedó "
    "(plata, salud, vínculos, y si logró o no su objetivo personal).\n"
    "\n"
    "Reportá en qué capítulo (1 a 7) está la escena actual en el campo "
    "\"capitulo\" de tu respuesta, avanzando de a poco en vez de saltear "
    "capítulos. NO se puede terminar la partida (\"es_final\": true) antes "
    "de llegar al capítulo 7, salvo que el personaje muera antes (salud a "
    "0) — en ese caso terminá ahí nomás, sin importar el capítulo.\n"
    "\n"
    "TRES CAMINOS (no se eligen con un menú: emergen de las decisiones "
    "acumuladas, igual que en el modo con guion fijo): un camino DENTRO DE "
    "LA LEY (asambleas, trueque, ayudar gente, denunciar), uno FUERA DE LA "
    "LEY (saquear, robar, violencia, piquetes violentos con gomas "
    "quemadas y bombas molotov), y uno AMBIVALENTE (mezcla de ambos). Vos "
    "llevás la cuenta de esto con el campo \"alineacion_delta\" en cada "
    "turno (negativo = ilegal, positivo = legal, poca magnitud si la acción "
    "es ambigua). El camino fuera de la ley tiene que ser MÁS DIFÍCIL: la "
    "mayoría de las veces que alguien va por ahí, termina preso, muerto, o "
    "de cartonero — pero dejá SIEMPRE abierta la posibilidad de un final "
    "\"referente_piquetero\" (ganar habiendo hecho solo cosas ilegales: "
    "piquetes violentos, molotovs, enfrentar a la policía, sin nunca ser "
    "capturado) para quien juegue ese camino de manera consistente y con "
    "suerte, como un logro raro y difícil, no como algo fácil de conseguir.\n"
    "\n"
    "Siempre que el personaje haga algo ilegal (robar, saquear, violencia, "
    "colarse en un control), tiene que existir la posibilidad real de que "
    "la policía lo persiga poco después — no lo dejes sin consecuencia "
    "sistemáticamente. En el camino, también puede sufrir un asalto o "
    "quedar atrapado en una manifestación ajena sin haberlo buscado.\n"
    "\n"
    "\"final_tipo\" (solo cuando \"es_final\" es true) tiene que ser "
    "EXACTAMENTE uno de estos valores, sin inventar otros: "
    "\"objetivo_cumplido\", \"comunidad\", \"solitario\", \"condenado\", "
    "\"muerte\", \"muerte_manifestacion\", \"cartonero\", "
    "\"referente_piquetero\", \"presidente\". Este último (\"presidente\": "
    "infiltrarse en la Casa Rosada desprotegida y terminar como presidente "
    "de la Nación) es un easter egg rarísimo, casi imposible de lograr por "
    "casualidad — no lo ofrezcas ni lo insinúes, que aparezca solo si el "
    "jugador se mete solo, por su cuenta, en una situación absurda como esa.\n"
    "\n"
    "ADAPTACIÓN POR BARRIO: el personaje va a decirte de qué barrio del "
    "Gran Buenos Aires o CABA sale. Usá tu propio conocimiento real de esa "
    "geografía para ajustar el tono, el nivel de riesgo y los detalles: no "
    "le pasan las mismas cosas ni de la misma manera a alguien de una zona "
    "acomodada (ej. San Isidro, Vicente López) que a alguien de una zona "
    "humilde del conurbano (ej. La Matanza, Lomas de Zamora) — pero la "
    "ESTRUCTURA de capítulos y los finales posibles son los mismos para "
    "cualquiera.\n"
    "\n"
    "Narrás en segunda persona ('estás', 'escuchás'), tono cinematográfico, "
    "neorrealista, crudo e inmersivo, con diálogos ocasionales de gente que "
    "se cruza en el camino. Usás dialecto rioplatense auténtico de la época "
    "('che', 'boludo', 'garca', 'ameo', 'chabón') con moderación, sin "
    "abusar. El inventario y la plata (pesos/Patacones/Lecops/créditos de "
    "trueque) tienen que crecer o achicarse según lo que el personaje "
    "compre, venda o trueque — nunca queden estáticos por mucho tiempo. "
    "Nunca describas ni generes contenido sexual.\n"
    "\n"
    "Respondé SIEMPRE y ÚNICAMENTE con un objeto JSON válido, sin texto "
    "antes ni después, sin bloques de markdown ni ```, con exactamente esta "
    "forma:\n"
    "{\n"
    '  "capitulo": 1,\n'
    '  "narracion": "3 a 6 oraciones en segunda persona",\n'
    '  "dialogos": [["Personaje", "línea corta de diálogo"]],\n'
    '  "opciones": ["opción táctica 1", "opción táctica 2", "opción táctica 3"],\n'
    '  "imagen_en": "descripción en inglés de la escena, en inglés, SOLO en '
    'momentos climáticos o de cambio de escenario, si no null",\n'
    '  "salud_delta": 0,\n'
    '  "dinero_delta": {"pesos": 0, "patacones": 0, "lecops": 0, "creditos_trueque": 0},\n'
    '  "inventario_add": [],\n'
    '  "inventario_quitar": [],\n'
    '  "reputacion_delta": 0,\n'
    '  "alineacion_delta": 0,\n'
    '  "es_final": false,\n'
    '  "final_tipo": null\n'
    "}\n"
    '"opciones" tiene que tener 3 o 4 entradas siempre que "es_final" sea '
    'false (si es true, dejala vacía: []). "dialogos" puede ser una lista '
    "vacía. Los deltas numéricos son enteros razonables (salud_delta entre "
    "-40 y 20, salvo un desenlace fatal)."
)


def _construir_mensaje_libre(
    historial: List[Dict[str, str]],
    estado_resumen: str,
    personaje: str,
    accion_jugador: str,
) -> str:
    lineas = [f"Personaje: {personaje}", f"Estado actual: {estado_resumen}", ""]
    if historial:
        lineas.append("Turnos recientes (resumidos), del más viejo al más nuevo:")
        for turno in historial:
            lineas.append(f"- Escena: {turno.get('narracion', '')}")
            lineas.append(f"  Jugador eligió: {turno.get('accion', '')}")
        lineas.append("")
    lineas.append(f'Acción del jugador ahora: "{accion_jugador}"')
    lineas.append("Generá el siguiente turno en el formato JSON indicado en las instrucciones.")
    return "\n".join(lineas)


def _parsear_json_llm(texto: str) -> Optional[Dict[str, Any]]:
    texto = (texto or "").strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto[:4].lower() == "json":
            texto = texto[4:]
    try:
        datos = json.loads(texto)
        return datos if isinstance(datos, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        try:
            datos = json.loads(texto[inicio:fin + 1])
            return datos if isinstance(datos, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _generar_json_con_anthropic(mensaje_usuario: str) -> Optional[Dict[str, Any]]:
    import anthropic

    cliente = anthropic.Anthropic()
    respuesta = cliente.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", MODELO_ANTHROPIC_POR_DEFECTO),
        max_tokens=900,
        system=SYSTEM_PROMPT_LIBRE,
        messages=[{"role": "user", "content": mensaje_usuario}],
    )
    bloques = [b.text for b in respuesta.content if getattr(b, "type", "") == "text"]
    return _parsear_json_llm("\n".join(bloques))


def _generar_json_con_gemini(mensaje_usuario: str) -> Optional[Dict[str, Any]]:
    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    respuesta = cliente.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", MODELO_GEMINI_POR_DEFECTO),
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_LIBRE,
            max_output_tokens=900,
            response_mime_type="application/json",
        ),
    )
    return _parsear_json_llm(getattr(respuesta, "text", None) or "")


def generar_turno_libre(
    historial: List[Dict[str, str]],
    estado_resumen: str,
    personaje: str,
    accion_jugador: str,
) -> Optional[Dict[str, Any]]:
    """Le pide al LLM el siguiente turno completo del modo libre.

    Devuelve el dict ya parseado (ver SYSTEM_PROMPT_LIBRE para la forma
    exacta) o None si no hay proveedor configurado, o si falla la llamada o
    el parseo del JSON por cualquier motivo. A diferencia de
    `generar_narracion`, acá no hay contenido fijo de respaldo: si esto
    devuelve None, quien llama tiene que mostrarle un error al jugador (el
    modo libre no tiene sentido sin LLM).
    """
    proveedor = _proveedor_activo()
    if proveedor is None or not modelo_configurado():
        return None

    mensaje = _construir_mensaje_libre(historial, estado_resumen, personaje, accion_jugador)

    try:
        if proveedor == "anthropic":
            return _generar_json_con_anthropic(mensaje)
        if proveedor == "gemini":
            return _generar_json_con_gemini(mensaje)
    except Exception:
        return None
    return None
