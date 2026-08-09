"""Motor del juego: conecta estado + historia + imágenes + texto libre + LLM.

Son funciones puras sobre un `EstadoJugador` (lo reciben y lo mutan in-place),
sin ningún I/O de terminal ni de red directa propia — por eso tanto `main.py`
(CLI) como `api/index.py` (web/Vercel) llaman exactamente a las mismas
funciones de acá y siempre ven el mismo comportamiento.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from game import free_text, images, llm, story
from game.state import Dinero, EstadoJugador, detectar_categoria_objetivo

NODO_INICIAL = "esquina_barrio"

INVENTARIO_INICIAL = ("libreta con anotaciones", "documento de identidad")

# A partir de este turno, en cualquier nodo no-final aparece una opción extra
# para cerrar la jornada. Sin esto, un jugador que nunca elige "quedarte a
# dormir en la asamblea" ni cae en el saqueo buscando a un familiar podría
# quedar dando vueltas entre esquina/banco/trueque/cibercafé sin llegar
# nunca a un final: esta opción garantiza que la partida siempre pueda
# terminar.
TURNO_LIMITE_CANSANCIO = 10
OPCION_TERMINAR_JORNADA = "Ya no das más por hoy: volver a tu casa a terminar la jornada"

# Eventos ambientales: viajar por el conurbano no es gratis. Cualquier vuelta
# a la esquina del barrio (el hub principal) tiene una chance chica de
# desviarte a un evento que no elegiste — un asalto, quedar en medio de una
# manifestación. Nunca en el primerísimo turno (recién arrancás la partida)
# ni dos veces seguidas (para no encadenar mala suerte sin parar).
NODOS_EVENTO_AMBIENTAL = ("asalto_callejero", "atrapado_manifestacion")
PROB_EVENTO_AMBIENTAL = 0.08


def _opcion_extra_disponible(estado: EstadoJugador, nodo) -> bool:
    return (
        not nodo.es_final
        and nodo.id != "calle_noche"
        and estado.turno >= TURNO_LIMITE_CANSANCIO
    )


def crear_estado(nombre: str, trasfondo: str, barrio: str, objetivo: str) -> EstadoJugador:
    """Arranca una partida nueva y devuelve el estado ya parado en el primer nodo."""
    categoria = detectar_categoria_objetivo(objetivo)
    estado = EstadoJugador(
        nombre=nombre.strip() or "Vecino/a sin nombre",
        trasfondo=trasfondo.strip() or "Alguien más tratando de llegar a fin de mes",
        barrio_inicial=barrio.strip() or "Un barrio del Conurbano",
        objetivo=objetivo.strip() or "Sobrevivir al día de hoy",
        objetivo_categoria=categoria,
    )
    estado.inventario = list(INVENTARIO_INICIAL)
    estado.dinero = Dinero(pesos=15, patacones=20, lecops=10)
    _entrar_nodo(estado, NODO_INICIAL)
    return estado


def elegir_final(estado: EstadoJugador) -> str:
    """Decide a qué final corresponde llegar según flags/reputación acumulados."""
    if not estado.vivo:
        return "final_muerte"

    categoria = estado.objetivo_categoria
    if categoria == "plata" and estado.tiene_flag("objetivo_cumplido_plata"):
        return "final_objetivo_cumplido"
    if categoria == "familiar" and estado.tiene_flag("buscando_familiar") and estado.reputacion_barrial >= 5:
        return "final_objetivo_cumplido"
    if categoria == "negocio" and estado.tiene_flag("defendiste_comercio"):
        return "final_objetivo_cumplido"

    if estado.reputacion_barrial >= 15:
        return "final_comunidad"
    return "final_solitario"


def _entrar_nodo(estado: EstadoJugador, nodo_id: str) -> None:
    if nodo_id == "final_decision":
        nodo_id = elegir_final(estado)

    if (
        nodo_id == "esquina_barrio"
        and estado.turno > 0
        and estado.nodo_actual not in NODOS_EVENTO_AMBIENTAL
        and random.random() < PROB_EVENTO_AMBIENTAL
    ):
        nodo_id = random.choice(NODOS_EVENTO_AMBIENTAL)

    nodo = story.obtener_nodo(nodo_id)
    estado.nodo_actual = nodo_id
    estado.ubicacion = nodo.ubicacion
    estado.turno += 1

    if nodo.salud_entrada != (0, 0):
        estado.salud += random.randint(*nodo.salud_entrada)
    estado.estados.update(nodo.estados_entrada)
    estado.salud_clamp()

    if nodo.imagen_en:
        estado.ultima_imagen_url = images.build_pollinations_url(nodo.imagen_en)
    else:
        estado.ultima_imagen_url = ""


def vista_actual(estado: EstadoJugador) -> Dict[str, Any]:
    """Construye la vista de un turno: lo que cualquier frontend necesita mostrar."""
    nodo = story.obtener_nodo(estado.nodo_actual)
    opciones_texto: List[str] = [op.texto for op in nodo.opciones] if not nodo.es_final else []
    if _opcion_extra_disponible(estado, nodo):
        opciones_texto.append(OPCION_TERMINAR_JORNADA)

    return {
        "turno": estado.turno,
        "ubicacion": nodo.ubicacion,
        "narracion": nodo.narracion,
        "dialogos": list(nodo.dialogos),
        "imagen_url": estado.ultima_imagen_url or None,
        "opciones": opciones_texto,
        "permite_libre": not nodo.es_final,
        "es_final": nodo.es_final,
        "final_tipo": nodo.final_tipo,
        "vivo": estado.vivo,
        "panel": {
            "ubicacion": nodo.ubicacion,
            "inventario": estado.descripcion_inventario(),
            "salud": estado.descripcion_salud(),
            "dinero": estado.dinero.describir(),
        },
        "mensaje_error": None,
        "mensaje_efecto": None,
        "mensaje_libre": None,
    }


def elegir_opcion(estado: EstadoJugador, indice_humano: int) -> Dict[str, Any]:
    """Aplica la opción táctica número `indice_humano` (1-based) y avanza la historia."""
    nodo = story.obtener_nodo(estado.nodo_actual)

    if nodo.es_final:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "La partida ya terminó. Empezá una nueva para seguir jugando."
        return vista

    idx = indice_humano - 1
    cantidad_opciones = len(nodo.opciones)

    if _opcion_extra_disponible(estado, nodo) and idx == cantidad_opciones:
        estado.salud += random.randint(-3, 3)
        estado.salud_clamp()
        destino = "final_muerte" if not estado.vivo else "calle_noche"
        _entrar_nodo(estado, destino)
        return vista_actual(estado)

    if idx < 0 or idx >= cantidad_opciones:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Esa opción no existe. Elegí un número de la lista o escribí una acción libre."
        return vista

    opcion = nodo.opciones[idx]

    if opcion.requiere_flag and not estado.tiene_flag(opcion.requiere_flag):
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Todavía no tenés forma de hacer eso."
        return vista
    if opcion.requiere_item and not estado.tiene_item(opcion.requiere_item):
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Te falta algo para poder hacer eso."
        return vista
    if opcion.excluye_flag and estado.tiene_flag(opcion.excluye_flag):
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Ya no podés hacer eso."
        return vista

    if opcion.salud_delta != (0, 0):
        estado.salud += random.randint(*opcion.salud_delta)
    estado.reputacion_barrial += opcion.reputacion_delta
    estado.dinero.aplicar(opcion.dinero_delta)
    estado.flags.update(opcion.flags_add)
    for f in opcion.flags_quitar:
        estado.flags.discard(f)
    for item in opcion.items_add:
        estado.agregar_item(item)
    for item in opcion.items_quitar:
        estado.quitar_item(item)
    estado.estados.update(opcion.estados_add)
    for e in opcion.estados_quitar:
        estado.estados.discard(e)
    estado.salud_clamp()

    if not estado.vivo:
        destino = "final_muerte"
    elif opcion.destino_alt and random.random() < opcion.prob_alt:
        destino = opcion.destino_alt
    else:
        destino = opcion.destino

    _entrar_nodo(estado, destino)
    vista = vista_actual(estado)
    if opcion.mensaje_efecto:
        vista["mensaje_efecto"] = opcion.mensaje_efecto

    if llm.modelo_configurado():
        nodo_nuevo = story.obtener_nodo(estado.nodo_actual)
        narracion_generada = llm.generar_narracion(
            contexto_escena=nodo.narracion,
            ubicacion=nodo_nuevo.ubicacion,
            accion_jugador=opcion.texto,
            resultado_mecanico=_guion_canonico(nodo_nuevo),
        )
        if narracion_generada:
            vista["narracion"] = narracion_generada

    return vista


def _guion_canonico(nodo) -> str:
    """Sinopsis "canónica" de un nodo: lo que el LLM tiene que narrar (con sus
    propias palabras) sin cambiar los hechos. Es la red de contención que
    garantiza que, haya o no LLM disponible, la historia sea siempre la misma."""
    guion = nodo.narracion
    if nodo.dialogos:
        citas = "; ".join(f'{personaje} dice algo como «{linea}»' for personaje, linea in nodo.dialogos)
        guion += (
            f" (Para referencia de tono, en este momento: {citas} — no repitas "
            "esa cita textual en tu narración, esas líneas ya se muestran aparte.)"
        )
    return guion


def _describir_resolucion_para_llm(resolucion: free_text.Resolucion) -> str:
    partes = []
    if resolucion.salud_delta:
        partes.append(f"salud {resolucion.salud_delta:+d}")
    if resolucion.reputacion_delta:
        partes.append(f"reputación barrial {resolucion.reputacion_delta:+d}")
    for clave, valor in resolucion.dinero_delta.items():
        if valor:
            partes.append(f"{clave} {valor:+d}")
    if resolucion.flags_add:
        partes.append("avanza la historia de forma relevante")
    if not partes:
        partes.append("sin cambios mecánicos significativos")
    return ", ".join(partes)


def accion_libre(estado: EstadoJugador, texto_jugador: str) -> Dict[str, Any]:
    """Procesa la opción "escribí tu propia acción" (opción 4)."""
    nodo = story.obtener_nodo(estado.nodo_actual)

    if nodo.es_final:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "La partida ya terminó. Empezá una nueva para seguir jugando."
        return vista

    texto_jugador = (texto_jugador or "").strip()
    if not texto_jugador:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Escribí algo primero."
        return vista

    resolucion = free_text.interpretar_accion_libre(estado, texto_jugador)

    estado.salud += resolucion.salud_delta
    estado.reputacion_barrial += resolucion.reputacion_delta
    estado.dinero.aplicar(resolucion.dinero_delta)
    estado.flags.update(resolucion.flags_add)
    estado.estados.update(resolucion.estados_add)
    estado.salud_clamp()

    narracion_libre = resolucion.narracion
    ubicacion_previa = nodo.ubicacion

    if not estado.vivo:
        destino = "final_muerte"
    else:
        destino = nodo.destino_libre or estado.nodo_actual

    _entrar_nodo(estado, destino)
    vista = vista_actual(estado)

    if llm.modelo_configurado():
        nodo_nuevo = story.obtener_nodo(estado.nodo_actual)
        resultado_mecanico = _describir_resolucion_para_llm(resolucion)
        if nodo_nuevo.id != nodo.id:
            # La acción libre te movió a otro nodo: contale al LLM también
            # el guion canónico de la escena nueva, no solo el delta.
            resultado_mecanico += f" Después de eso: {_guion_canonico(nodo_nuevo)}"
        narracion_generada = llm.generar_narracion(
            contexto_escena=nodo.narracion,
            ubicacion=ubicacion_previa,
            accion_jugador=texto_jugador,
            resultado_mecanico=resultado_mecanico,
        )
        if narracion_generada:
            narracion_libre = narracion_generada

    vista["mensaje_libre"] = narracion_libre
    return vista


def guardar_estado(estado: EstadoJugador) -> Dict[str, Any]:
    return estado.to_dict()


def cargar_estado(datos: Dict[str, Any]) -> EstadoJugador:
    return EstadoJugador.from_dict(datos)
