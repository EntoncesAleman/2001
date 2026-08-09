"""Lógica de salas multijugador: crear, unirse, arrancar, jugar turnos y
cerrar la partida. Es la única parte de v2 con reglas de negocio — v2/app.py
solo traduce esto a rutas HTTP/Socket.IO.

Reutiliza game/engine.py, game/story.py y game/state.py del v1 TAL CUAL, sin
tocarlos: cada jugador de la sala tiene su propio EstadoJugador (mismo
dataclass que el modo un-jugador), serializado en la columna jsonb
`estado_json` de la tabla `jugadores`. Lo que agrega v2 es la capa de sala
compartida (Supabase en vez de una cookie), el feed de eventos, y las
condiciones de arranque/cierre de una partida de mesa.
"""

from __future__ import annotations

import os
import random
import string
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import engine, story  # noqa: E402
from game.state import EstadoJugador  # noqa: E402

from supabase_client import obtener_cliente  # noqa: E402

MIN_JUGADORES_DEFAULT = 3
MAX_JUGADORES_DEFAULT = 6
# Presupuesto de turnos compartido por toda la mesa antes de que "se acaben
# los días". Calibrado sobre los golden paths del v1 (un solo jugador
# necesita ~17-23 turnos jugando de forma óptima, bastante más jugando al
# azar/explorando sidequests) — con 300 turnos repartidos entre 3 y 6
# jugadores le queda a cada uno margen real para llegar a un final y de paso
# explorar, no solo para el camino más corto posible.
LIMITE_TURNOS_DEFAULT = 300

# Alfabeto sin caracteres ambiguos (0/O, 1/I/L) para que el código de sala se
# pueda transcribir de palabra sin confusiones.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# Flags "notables": cuando un jugador las suma, se anuncian en el feed
# compartido de la sala (todo el mundo se entera de los hitos de todos,
# aunque cada uno juegue su propio personaje). Ver anunciar_hitos_nuevos().
HITOS_COMPARTIDOS = {
    "defendiste_comercio": "defendió un comercio de un saqueo",
    "trabajaste_de_cartonero": "se subió al tren de los cartoneros",
    "ayudaste_en_represion": "ayudó a alguien caído en una represión",
    "tiraste_molotov": "tiró una molotov en un piquete",
    "mision_comedor_completa": "completó el mandado de Doña Rosa",
    "objetivo_cumplido_plata": "logró sacar sus ahorros del banco",
    "buscando_familiar": "encontró una pista de la persona que buscaba",
}

# mundo_flags que un jugador puede "gastar" para el resto de la mesa: una
# vez que alguien resuelve el saqueo del supermercado (para bien o para
# mal), el resto de la sala lo encuentra ya resuelto. Es una anotación
# informativa (un mensaje extra en su turno) — no reescribe las reglas del
# nodo en sí, que siguen siendo las de game/story.py sin modificar.
_FLAGS_QUE_RESUELVEN_SAQUEO = ("defendiste_comercio",)
_NODOS_SAQUEO = ("saqueo_supermercado", "saqueo_participar", "saqueo_ayudar_dueno")


def _cliente():
    return obtener_cliente()


def generar_codigo_sala() -> str:
    return "".join(random.choices(_ALFABETO_CODIGO, k=5))


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Salas
# ---------------------------------------------------------------------------

def crear_sala(modo: str = "historia") -> Dict[str, Any]:
    if modo not in ("historia", "libre"):
        modo = "historia"
    cliente = _cliente()
    for _ in range(5):
        codigo = generar_codigo_sala()
        existente = cliente.table("salas").select("id").eq("codigo", codigo).execute()
        if not existente.data:
            break
    else:
        raise RuntimeError("no se pudo generar un código de sala único")

    fila = {
        "codigo": codigo,
        "modo": modo,
        "estado": "esperando",
        "min_jugadores": MIN_JUGADORES_DEFAULT,
        "max_jugadores": MAX_JUGADORES_DEFAULT,
        "limite_turnos": LIMITE_TURNOS_DEFAULT,
    }
    resultado = cliente.table("salas").insert(fila).execute()
    return resultado.data[0]


def obtener_sala(sala_id: str) -> Optional[Dict[str, Any]]:
    resultado = _cliente().table("salas").select("*").eq("id", sala_id).execute()
    return resultado.data[0] if resultado.data else None


def obtener_sala_por_codigo(codigo: str) -> Optional[Dict[str, Any]]:
    resultado = (
        _cliente().table("salas").select("*").eq("codigo", codigo.strip().upper()).execute()
    )
    return resultado.data[0] if resultado.data else None


def listar_jugadores(sala_id: str) -> List[Dict[str, Any]]:
    resultado = (
        _cliente()
        .table("jugadores")
        .select("*")
        .eq("sala_id", sala_id)
        .order("unido_en")
        .execute()
    )
    return resultado.data


def registrar_evento(sala_id: str, tipo: str, mensaje: str, jugador_id: Optional[str] = None) -> Dict[str, Any]:
    fila = {"sala_id": sala_id, "tipo": tipo, "mensaje": mensaje, "jugador_id": jugador_id}
    resultado = _cliente().table("eventos").insert(fila).execute()
    return resultado.data[0]


def listar_eventos_desde(sala_id: str, desde_id: int = 0) -> List[Dict[str, Any]]:
    resultado = (
        _cliente()
        .table("eventos")
        .select("*")
        .eq("sala_id", sala_id)
        .gt("id", desde_id)
        .order("id")
        .execute()
    )
    return resultado.data


# ---------------------------------------------------------------------------
# Jugadores: unirse y arrancar la sala
# ---------------------------------------------------------------------------

class ErrorSala(Exception):
    """Error de reglas de negocio (sala llena, ya arrancó, nombre repetido...)."""


def unirse_a_sala(codigo: str, nombre: str, trasfondo: str, barrio: str, objetivo: str) -> Tuple[Dict, Dict]:
    sala = obtener_sala_por_codigo(codigo)
    if sala is None:
        raise ErrorSala("No existe ninguna sala con ese código.")
    if sala["estado"] != "esperando":
        raise ErrorSala("Esta partida ya arrancó o ya terminó — no se puede sumar gente a mitad de camino.")

    jugadores_actuales = listar_jugadores(sala["id"])
    if len(jugadores_actuales) >= sala["max_jugadores"]:
        raise ErrorSala(f"La sala ya tiene el máximo de {sala['max_jugadores']} jugadores.")
    if any(j["nombre"].strip().lower() == nombre.strip().lower() for j in jugadores_actuales):
        raise ErrorSala("Ya hay alguien en esta sala con ese nombre — elegí otro.")

    estado = engine.crear_estado(nombre, trasfondo, barrio, objetivo)
    es_anfitrion = len(jugadores_actuales) == 0

    fila = _fila_desde_estado(sala["id"], estado)
    fila["es_anfitrion"] = es_anfitrion
    resultado = _cliente().table("jugadores").insert(fila).execute()
    jugador = resultado.data[0]

    registrar_evento(sala["id"], "union", f"{nombre} se sumó a la mesa.", jugador["id"])

    sala = intentar_iniciar_sala(sala["id"]) or sala
    return sala, jugador


def intentar_iniciar_sala(sala_id: str) -> Optional[Dict[str, Any]]:
    sala = obtener_sala(sala_id)
    if sala is None or sala["estado"] != "esperando":
        return sala
    cantidad = len(listar_jugadores(sala_id))
    if cantidad < sala["min_jugadores"]:
        return sala
    resultado = (
        _cliente()
        .table("salas")
        .update({"estado": "en_curso", "iniciada_en": _ahora()})
        .eq("id", sala_id)
        .execute()
    )
    registrar_evento(sala_id, "arranque", f"La partida arrancó con {cantidad} jugadores.")
    return resultado.data[0]


# ---------------------------------------------------------------------------
# Estado del jugador: ida y vuelta con game/state.py:EstadoJugador
# ---------------------------------------------------------------------------

def _fila_desde_estado(sala_id: str, estado: EstadoJugador, es_anfitrion: bool = False) -> Dict[str, Any]:
    nodo = story.obtener_nodo(estado.nodo_actual)
    return {
        "sala_id": sala_id,
        "nombre": estado.nombre,
        "trasfondo": estado.trasfondo,
        "barrio_inicial": estado.barrio_inicial,
        "objetivo": estado.objetivo,
        "objetivo_categoria": estado.objetivo_categoria,
        "zona_gba": estado.zona_gba,
        "nodo_actual": estado.nodo_actual,
        "ubicacion": estado.ubicacion,
        "salud": estado.salud,
        "inventario": list(estado.inventario),
        "dinero": estado.dinero.to_dict(),
        "flags": sorted(estado.flags),
        "estados": sorted(estado.estados),
        "reputacion_barrial": estado.reputacion_barrial,
        "alineacion": estado.alineacion,
        "capitulo": estado.capitulo,
        "turno": estado.turno,
        "vivo": estado.vivo,
        "orden_opciones": list(estado.orden_opciones),
        "es_final": nodo.es_final,
        "final_tipo": nodo.final_tipo if nodo.es_final else None,
        "puntaje": estado.generar_estadisticas(nodo.final_tipo if nodo.es_final else None)["puntaje"],
        "es_anfitrion": es_anfitrion,
        "estado_json": estado.to_dict(),
        "actualizado_en": _ahora(),
    }


def cargar_estado_jugador(jugador_row: Dict[str, Any]) -> EstadoJugador:
    return EstadoJugador.from_dict(jugador_row["estado_json"])


def obtener_jugador(jugador_id: str) -> Optional[Dict[str, Any]]:
    resultado = _cliente().table("jugadores").select("*").eq("id", jugador_id).execute()
    return resultado.data[0] if resultado.data else None


def guardar_estado_jugador(jugador_id: str, sala_id: str, estado: EstadoJugador) -> Dict[str, Any]:
    fila = _fila_desde_estado(sala_id, estado)
    fila.pop("sala_id", None)  # no se reescribe la FK en el update
    resultado = _cliente().table("jugadores").update(fila).eq("id", jugador_id).execute()
    return resultado.data[0]


# ---------------------------------------------------------------------------
# Jugar un turno
# ---------------------------------------------------------------------------

def _anunciar_hitos_nuevos(sala_id: str, jugador_id: str, nombre: str, flags_antes: set, flags_despues: set) -> None:
    nuevas = flags_despues - flags_antes
    for flag in nuevas:
        descripcion = HITOS_COMPARTIDOS.get(flag)
        if descripcion:
            registrar_evento(sala_id, "hito", f"{nombre} {descripcion}.", jugador_id)


def _mundo_anotar_saqueo_si_corresponde(sala_id: str, jugador_id: str, estado: EstadoJugador) -> None:
    """Anotación informativa de "mundo compartido": si alguien ya resolvió el
    saqueo del supermercado, se guarda en mundo_flags para que la vista de
    los demás jugadores lo mencione (ver anotar_vista_con_mundo). No cambia
    las reglas del nodo — eso vive en game/story.py, sin tocar."""
    if not any(f in estado.flags for f in _FLAGS_QUE_RESUELVEN_SAQUEO):
        return
    cliente = _cliente()
    ya_existe = (
        cliente.table("mundo_flags")
        .select("flag")
        .eq("sala_id", sala_id)
        .eq("flag", "saqueo_resuelto")
        .execute()
    )
    if ya_existe.data:
        return
    cliente.table("mundo_flags").insert(
        {"sala_id": sala_id, "flag": "saqueo_resuelto", "valor": True, "jugador_id": jugador_id}
    ).execute()
    registrar_evento(
        sala_id, "mundo", f"{estado.nombre} dejó el supermercado del barrio resuelto para el resto de la mesa."
    )


def anotar_vista_con_mundo(sala_id: str, vista: Dict[str, Any]) -> Dict[str, Any]:
    """Si el jugador entra a un nodo de saqueo y ya está marcado como
    resuelto por otro jugador de la sala, se lo avisamos con un mensaje
    extra — sin alterar las opciones reales del nodo."""
    if vista.get("es_final"):
        return vista
    nodo_actual_es_saqueo = any(
        vista.get("ubicacion", "").lower().startswith(pref)
        for pref in ("supermercado",)
    )
    if not nodo_actual_es_saqueo:
        return vista
    resultado = (
        _cliente()
        .table("mundo_flags")
        .select("flag")
        .eq("sala_id", sala_id)
        .eq("flag", "saqueo_resuelto")
        .execute()
    )
    if resultado.data:
        aviso = "Un vecino de la mesa ya pasó por acá antes que vos: se nota que esto ya se resolvió de alguna manera."
        vista["mensaje_efecto"] = (vista.get("mensaje_efecto") or "") + " " + aviso
    return vista


def jugar_opcion(jugador_id: str, indice_humano: int) -> Dict[str, Any]:
    jugador_row = obtener_jugador(jugador_id)
    if jugador_row is None:
        raise ErrorSala("Ese jugador no existe (¿la sala se cerró?).")
    sala = obtener_sala(jugador_row["sala_id"])
    if sala is None or sala["estado"] != "en_curso":
        raise ErrorSala("La partida no está en curso.")

    estado = cargar_estado_jugador(jugador_row)
    if not story.obtener_nodo(estado.nodo_actual).es_final:
        flags_antes = set(estado.flags)
        vista = engine.elegir_opcion(estado, indice_humano)
        _anunciar_hitos_nuevos(sala["id"], jugador_id, estado.nombre, flags_antes, set(estado.flags))
        _mundo_anotar_saqueo_si_corresponde(sala["id"], jugador_id, estado)
    else:
        vista = engine.vista_actual(estado)

    guardar_estado_jugador(jugador_id, sala["id"], estado)
    _cliente().table("salas").update({"turno_global": sala["turno_global"] + 1}).eq("id", sala["id"]).execute()

    nodo = story.obtener_nodo(estado.nodo_actual)
    if nodo.es_final:
        registrar_evento(
            sala["id"], "final_personal", f"{estado.nombre} llegó a un final: {nodo.final_tipo}.", jugador_id
        )

    verificar_fin_de_partida(sala["id"])
    vista = anotar_vista_con_mundo(sala["id"], vista)
    return vista


def jugar_accion_libre(jugador_id: str, texto: str) -> Dict[str, Any]:
    jugador_row = obtener_jugador(jugador_id)
    if jugador_row is None:
        raise ErrorSala("Ese jugador no existe (¿la sala se cerró?).")
    sala = obtener_sala(jugador_row["sala_id"])
    if sala is None or sala["estado"] != "en_curso":
        raise ErrorSala("La partida no está en curso.")

    estado = cargar_estado_jugador(jugador_row)
    flags_antes = set(estado.flags)
    vista = engine.accion_libre(estado, texto)
    _anunciar_hitos_nuevos(sala["id"], jugador_id, estado.nombre, flags_antes, set(estado.flags))
    _mundo_anotar_saqueo_si_corresponde(sala["id"], jugador_id, estado)

    guardar_estado_jugador(jugador_id, sala["id"], estado)
    _cliente().table("salas").update({"turno_global": sala["turno_global"] + 1}).eq("id", sala["id"]).execute()

    verificar_fin_de_partida(sala["id"])
    vista = anotar_vista_con_mundo(sala["id"], vista)
    return vista


# ---------------------------------------------------------------------------
# Fin de partida
# ---------------------------------------------------------------------------

def verificar_fin_de_partida(sala_id: str) -> Optional[Dict[str, Any]]:
    """"Pierden todos si se acaban los turnos compartidos de la mesa y nadie
    completó su misión; si no, gana quien tenga más puntaje" — tal cual lo
    pedido. También cierra la partida antes de tiempo si todos los
    jugadores ya llegaron a su final personal (no tiene sentido seguir
    esperando)."""
    sala = obtener_sala(sala_id)
    if sala is None or sala["estado"] != "en_curso":
        return sala

    jugadores = listar_jugadores(sala_id)
    todos_terminaron = jugadores and all(j["es_final"] or not j["vivo"] for j in jugadores)
    se_acabo_el_tiempo = sala["turno_global"] >= sala["limite_turnos"]

    if not todos_terminaron and not se_acabo_el_tiempo:
        return sala

    alguien_cumplio_objetivo = any(j["final_tipo"] == "objetivo_cumplido" for j in jugadores)
    if not alguien_cumplio_objetivo:
        actualizacion = {"estado": "terminada", "resultado": "derrota_colectiva", "terminada_en": _ahora()}
        registrar_evento(sala_id, "cierre", "Se acabó el tiempo y nadie logró su misión: pierde toda la mesa.")
    else:
        ganador = max(jugadores, key=lambda j: j["puntaje"])
        actualizacion = {
            "estado": "terminada",
            "resultado": "gano_jugador",
            "ganador_jugador_id": ganador["id"],
            "terminada_en": _ahora(),
        }
        registrar_evento(
            sala_id,
            "cierre",
            f"{ganador['nombre']} gana la mesa con {ganador['puntaje']} puntos.",
            ganador["id"],
        )

    resultado = _cliente().table("salas").update(actualizacion).eq("id", sala_id).execute()
    return resultado.data[0]
