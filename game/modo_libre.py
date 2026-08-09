"""Motor del "modo libre": sin grafo de nodos fijo, la historia completa la
maneja un LLM (Gemini o Claude) en formato JSON estructurado, turno a turno.

A diferencia de `game/engine.py` (modo historia), acá no hay ningún
contenido de respaldo: si no hay una API key configurada, o la llamada
falla, no hay forma de seguir jugando — por eso este modo solo se ofrece en
el frontend cuando `game/llm.py:modelo_configurado()` da True, y cada
función de acá devuelve un error explícito en vez de inventar algo.

El estado del jugador (`EstadoJugador`) es el mismo objeto que usa el modo
historia: inventario, dinero y salud funcionan igual. Lo único que cambia es
que la escena/opciones/desenlace no vienen de `game/story.py` sino de lo
último que respondió el modelo (guardado en `estado.escena_libre`,
`estado.opciones_libres`, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from game import images, llm
from game.state import Dinero, EstadoJugador, detectar_categoria_objetivo, resumen_camino

# Cuántos turnos recientes se le mandan al modelo como contexto. Tiene que
# ser chico: el estado completo viaja en una cookie de sesión firmada (no
# hay base de datos), así que no puede crecer sin límite.
MAX_HISTORIAL_TURNOS = 6
MAX_LARGO_RESUMEN = 320

INVENTARIO_INICIAL = ("libreta con anotaciones", "documento de identidad")

# Mismo vocabulario de finales que game/story.py (ver game/engine.py). Si el
# LLM devuelve cualquier otra cosa en "final_tipo", se cae a "solitario" en
# vez de mostrarle al jugador un final_tipo inventado que ningún frontend
# sabe traducir a una etiqueta.
FINALES_VALIDOS = {
    "objetivo_cumplido",
    "comunidad",
    "solitario",
    "condenado",
    "muerte",
    "muerte_manifestacion",
    "cartonero",
    "referente_piquetero",
    "presidente",
    "represion_derrota",
    "perdido",
}

CAPITULO_MINIMO_PARA_TERMINAR = 7


def _resumen(texto: str) -> str:
    texto = (texto or "").strip()
    if len(texto) <= MAX_LARGO_RESUMEN:
        return texto
    return texto[:MAX_LARGO_RESUMEN].rsplit(" ", 1)[0] + "…"


def _estado_resumen(estado: EstadoJugador) -> str:
    return (
        f"Capítulo actual: {estado.capitulo} de 7. "
        f"Ubicación: {estado.ubicacion}. Salud: {estado.descripcion_salud()}. "
        f"Inventario y plata: {estado.descripcion_inventario()}. "
        f"Reputación barrial: {estado.reputacion_barrial}. "
        f"Alineación legal/ilegal: {estado.alineacion} (negativo = viene actuando fuera "
        f"de la ley, positivo = dentro de la ley, cerca de 0 = ambivalente)."
    )


def _personaje_resumen(estado: EstadoJugador) -> str:
    return (
        f"{estado.nombre}, {estado.trasfondo}, de {estado.barrio_inicial}. "
        f"Objetivo principal: {estado.objetivo}."
    )


def _agregar_historial(estado: EstadoJugador, accion: str, narracion: str) -> None:
    estado.historial_libre.append({"accion": _resumen(accion), "narracion": _resumen(narracion)})
    if len(estado.historial_libre) > MAX_HISTORIAL_TURNOS:
        estado.historial_libre = estado.historial_libre[-MAX_HISTORIAL_TURNOS:]


def _aplicar_respuesta(estado: EstadoJugador, respuesta: Dict[str, Any]) -> None:
    try:
        salud_delta = int(respuesta.get("salud_delta") or 0)
    except (TypeError, ValueError):
        salud_delta = 0
    salud_delta = max(-60, min(30, salud_delta))
    estado.salud += salud_delta

    dinero_delta = respuesta.get("dinero_delta")
    if isinstance(dinero_delta, dict):
        delta_limpio = {}
        for clave in ("pesos", "patacones", "lecops", "creditos_trueque"):
            try:
                delta_limpio[clave] = int(dinero_delta.get(clave, 0) or 0)
            except (TypeError, ValueError):
                delta_limpio[clave] = 0
        estado.dinero.aplicar(delta_limpio)

    for item in list(respuesta.get("inventario_add") or [])[:5]:
        estado.agregar_item(str(item)[:120])
    for item in list(respuesta.get("inventario_quitar") or [])[:5]:
        estado.quitar_item(str(item))

    try:
        reputacion_delta = int(respuesta.get("reputacion_delta") or 0)
    except (TypeError, ValueError):
        reputacion_delta = 0
    estado.reputacion_barrial += max(-20, min(20, reputacion_delta))

    try:
        alineacion_delta = int(respuesta.get("alineacion_delta") or 0)
    except (TypeError, ValueError):
        alineacion_delta = 0
    estado.alineacion = max(-100, min(100, estado.alineacion + max(-25, min(25, alineacion_delta))))

    try:
        capitulo_reportado = int(respuesta.get("capitulo") or estado.capitulo)
    except (TypeError, ValueError):
        capitulo_reportado = estado.capitulo
    # Nunca retrocede ni salta capítulos de a más de uno: es la red de
    # contención para que el LLM no se dé cuenta la mitad de la campaña ni
    # se quede dando vueltas en el capítulo 1 para siempre.
    estado.capitulo = max(estado.capitulo, min(capitulo_reportado, estado.capitulo + 1))
    estado.capitulo = max(1, min(7, estado.capitulo))

    estado.salud_clamp()

    ubicacion_reportada = str(respuesta.get("ubicacion") or "").strip()
    if ubicacion_reportada:
        estado.ubicacion = ubicacion_reportada[:120]
    estado.lugares_visitados.add(estado.ubicacion)

    estado.escena_libre = str(respuesta.get("narracion") or "").strip() or "..."

    dialogos_crudos = respuesta.get("dialogos") or []
    dialogos: List[tuple] = []
    if isinstance(dialogos_crudos, list):
        for entrada in dialogos_crudos[:2]:
            if isinstance(entrada, (list, tuple)) and len(entrada) == 2:
                dialogos.append((str(entrada[0])[:60], str(entrada[1])[:300]))
    estado.dialogos_libres = dialogos

    opciones_crudas = respuesta.get("opciones") or []
    opciones = [str(o)[:200] for o in opciones_crudas if str(o).strip()][:4] if isinstance(opciones_crudas, list) else []

    imagen_en = respuesta.get("imagen_en")
    if imagen_en and estado.vivo:
        estado.ultima_imagen_url = images.build_pollinations_url(str(imagen_en)[:500])
    else:
        estado.ultima_imagen_url = ""

    es_final = bool(respuesta.get("es_final"))
    if not estado.vivo:
        es_final = True
        final_tipo = "muerte_manifestacion" if estado.capitulo in (2, 3) else "muerte"
        estado.final_tipo_libre = final_tipo
    elif es_final and estado.capitulo < CAPITULO_MINIMO_PARA_TERMINAR:
        # Regla inquebrantable: no se puede terminar la partida antes de
        # llegar al cierre (capítulo 7), salvo que el personaje haya muerto
        # (ya cubierto arriba). Si el LLM intenta cortar antes de tiempo, se
        # ignora ese "es_final" y la historia sigue.
        es_final = False
    elif es_final:
        final_tipo_reportado = str(respuesta.get("final_tipo") or "").strip()
        estado.final_tipo_libre = final_tipo_reportado if final_tipo_reportado in FINALES_VALIDOS else "solitario"

    estado.opciones_libres = [] if es_final else opciones
    estado.es_final_libre = es_final


def iniciar_partida_libre(nombre: str, trasfondo: str, barrio: str, objetivo: str) -> Optional[EstadoJugador]:
    """Devuelve el estado ya con la primera escena generada, o None si no
    hay ningún LLM configurado o falló la primera llamada."""
    if not llm.modelo_configurado():
        return None

    categoria = detectar_categoria_objetivo(objetivo)
    estado = EstadoJugador(
        nombre=nombre.strip() or "Vecino/a sin nombre",
        trasfondo=trasfondo.strip() or "Alguien más tratando de llegar a fin de mes",
        barrio_inicial=barrio.strip() or "Un barrio del Conurbano",
        objetivo=objetivo.strip() or "Sobrevivir al día de hoy",
        objetivo_categoria=categoria,
    )
    estado.modo = "libre"
    estado.inventario = list(INVENTARIO_INICIAL)
    estado.dinero = Dinero(pesos=15, patacones=20, lecops=10)
    estado.ubicacion = f"Esquina de {estado.barrio_inicial}, Gran Buenos Aires"

    respuesta = llm.generar_turno_libre(
        historial=[],
        estado_resumen=_estado_resumen(estado),
        personaje=_personaje_resumen(estado),
        accion_jugador="(inicio de la partida: presentá la primera escena y el primer conflicto de alto impacto)",
    )
    if respuesta is None:
        return None

    _aplicar_respuesta(estado, respuesta)
    _agregar_historial(estado, "(inicio de partida)", estado.escena_libre)
    estado.turno = 1
    return estado


def vista_actual_libre(estado: EstadoJugador) -> Dict[str, Any]:
    return {
        "turno": estado.turno,
        "ubicacion": estado.ubicacion,
        "narracion": estado.escena_libre,
        "dialogos": [list(d) for d in estado.dialogos_libres],
        "imagen_url": estado.ultima_imagen_url or None,
        "opciones": list(estado.opciones_libres),
        "permite_libre": not estado.es_final_libre,
        "es_final": estado.es_final_libre,
        "final_tipo": estado.final_tipo_libre,
        "vivo": estado.vivo,
        "panel": {
            "ubicacion": estado.ubicacion,
            "inventario": estado.descripcion_inventario(),
            "salud": estado.descripcion_salud(),
            "dinero": estado.dinero.describir(),
            "dia": estado.etiqueta_capitulo(),
            "mision": estado.objetivo,
            "camino": resumen_camino(estado.alineacion),
        },
        "estadisticas": estado.generar_estadisticas(estado.final_tipo_libre) if estado.es_final_libre else None,
        "mensaje_error": None,
        "mensaje_efecto": None,
        "mensaje_libre": None,
        "modo": "libre",
    }


def _procesar_turno(estado: EstadoJugador, accion_jugador: str) -> Dict[str, Any]:
    if estado.es_final_libre:
        vista = vista_actual_libre(estado)
        vista["mensaje_error"] = "La partida ya terminó. Empezá una nueva para seguir jugando."
        return vista

    respuesta = llm.generar_turno_libre(
        historial=estado.historial_libre,
        estado_resumen=_estado_resumen(estado),
        personaje=_personaje_resumen(estado),
        accion_jugador=accion_jugador,
    )
    if respuesta is None:
        vista = vista_actual_libre(estado)
        vista["mensaje_error"] = (
            "No se pudo generar el siguiente turno (sin conexión, límite de uso, o la API "
            "key dejó de funcionar). Probá de nuevo en un momento."
        )
        return vista

    _agregar_historial(estado, accion_jugador, estado.escena_libre)
    _aplicar_respuesta(estado, respuesta)
    estado.turno += 1
    return vista_actual_libre(estado)


def elegir_opcion_libre(estado: EstadoJugador, indice_humano: int) -> Dict[str, Any]:
    idx = indice_humano - 1
    if idx < 0 or idx >= len(estado.opciones_libres):
        vista = vista_actual_libre(estado)
        vista["mensaje_error"] = "Esa opción no existe. Elegí un número de la lista o escribí una acción libre."
        return vista
    return _procesar_turno(estado, estado.opciones_libres[idx])


def accion_libre_libre(estado: EstadoJugador, texto_jugador: str) -> Dict[str, Any]:
    texto_jugador = (texto_jugador or "").strip()
    if not texto_jugador:
        vista = vista_actual_libre(estado)
        vista["mensaje_error"] = "Escribí algo primero."
        return vista
    return _procesar_turno(estado, texto_jugador)


def guardar_estado(estado: EstadoJugador) -> Dict[str, Any]:
    return estado.to_dict()


def cargar_estado(datos: Dict[str, Any]) -> EstadoJugador:
    return EstadoJugador.from_dict(datos)
