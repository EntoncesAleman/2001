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
from game.state import (
    Dinero,
    EstadoJugador,
    ZONA_INFO,
    detectar_categoria_objetivo,
    detectar_zona_gba,
    mensaje_cambio_camino,
    resumen_camino,
)

# El primer nodo depende de qué objetivo eligió el jugador al crear el
# personaje: la aventura puede *empezar* de formas distintas (así no hay una
# única secuencia de números para aprenderse de memoria) pero todas
# convergen al mismo Capítulo 1 (esquina_barrio) en 1-2 turnos.
NODO_INICIAL_POR_CATEGORIA = {
    "plata": "inicio_plata",
    "familiar": "inicio_familiar",
    "negocio": "inicio_negocio",
    "escape": "inicio_generico",
    "generico": "inicio_generico",
}

INVENTARIO_INICIAL = ("libreta con anotaciones", "documento de identidad")

# Nodo "hub" vigente según el capítulo actual de la campaña. Los nodos de
# servicio (hospital, trueque, comedor, mercado negro, control de ruta,
# cibercafé, asamblea, persecución, eventos ambientales...) no vuelven a un
# nodo fijo: usan el destino sentinel "volver_al_hub", que acá se resuelve
# al hub del capítulo en el que esté el jugador en ese momento. Así el mismo
# nodo de servicio sirve en cualquier capítulo sin tener que duplicarlo.
HUB_POR_CAPITULO = {
    1: "esquina_barrio",
    2: "esquina_barrio",
    3: "amanecer_20",
    4: "semana_presidentes_1",
    5: "semana_presidentes_2",
    6: "semana_presidentes_3",
    7: "calle_noche",
}

# A partir de este turno, cualquier nodo "hub" (los que definen
# `destino_cansancio` en game/story.py) ofrece una opción extra para cerrar
# la escena y avanzar al siguiente capítulo. Sin esto, alguien podría quedar
# dando vueltas para siempre entre banco/asamblea/trueque sin avanzar nunca
# la historia: esta opción garantiza que la partida siempre pueda progresar.
# Es la base "neutra"; el margen real de cada jugador varía según su zona
# del GBA (ver _limite_cansancio) porque viajar desde el Oeste o desde
# Zona Norte come mucho más día que moverse dentro de CABA.
TURNO_LIMITE_CANSANCIO_BASE = 8
TURNO_LIMITE_CANSANCIO_MINIMO = 5

# Cuántos turnos puede quedar "colgado" el mandado de Doña Rosa (comedor)
# antes de darlo por perdido: sin este límite, un jugador podría dejarlo
# aceptado indefinidamente sin costo alguno.
TURNO_LIMITE_COMEDOR = 6
OPCION_TERMINAR_JORNADA = "Ya no das más por ahora: seguir adelante con el día"

# Eventos ambientales: viajar por el conurbano no es gratis. Cualquier vuelta
# a la esquina del barrio (el hub principal del Capítulo 1) tiene una chance
# chica de desviarte a un evento que no elegiste — un asalto, quedar en
# medio de una manifestación, o una demora de transporte con sabor a la zona
# de la que sale el personaje (el Sarmiento, el Mitre, el Roca, o subte/
# colectivo si es de CABA). Nunca en el primerísimo turno ni dos veces
# seguidas (para no encadenar mala suerte sin parar).
DEMORA_TRANSPORTE_POR_ZONA = {
    "caba": "demora_transporte_caba",
    "zona_norte": "demora_transporte_zona_norte",
    "zona_oeste": "demora_transporte_zona_oeste",
    "zona_sur": "demora_transporte_zona_sur",
    "conurbano_generico": "demora_transporte_generico",
}
CATEGORIAS_EVENTO_AMBIENTAL = ("asalto_callejero", "atrapado_manifestacion", "demora_transporte")
NODOS_EVENTO_AMBIENTAL = ("asalto_callejero", "atrapado_manifestacion") + tuple(
    DEMORA_TRANSPORTE_POR_ZONA.values()
)
PROB_EVENTO_AMBIENTAL = 0.08


def _limite_cansancio(estado: EstadoJugador) -> int:
    """Cuántos turnos aguanta el día antes de que aparezca la opción de
    cerrarlo, según la zona del GBA/CABA de la que sale el personaje (ver
    game/state.py:ZONA_INFO). Vivir lejos y depender de un tren colapsado
    (el Sarmiento, típicamente) come margen real del día."""
    ajuste = ZONA_INFO.get(estado.zona_gba, ZONA_INFO["conurbano_generico"])["ajuste_cansancio"]
    return max(TURNO_LIMITE_CANSANCIO_MINIMO, TURNO_LIMITE_CANSANCIO_BASE + ajuste)

# Si la salud llega a 0 estando en uno de estos nodos, el final es
# "final_muerte_manifestacion" (una bala perdida, gases, una topadora) en vez
# del genérico "final_muerte" — mismo mecanismo de siempre, solo cambia el
# nodo de destino según dónde te agarró.
NODOS_CONTEXTO_MANIFESTACION = {
    "cacerolazo_19",
    "plaza_de_mayo",
    "piquetero_violento_1",
    "piquetero_violento_2",
    "represion",
    "represion_herido",
    "atrapado_manifestacion",
    "piquete",
    "piquete_resistencia",
    "piquete_represion",
}


def _destino_muerte(estado: EstadoJugador) -> str:
    if estado.nodo_actual in NODOS_CONTEXTO_MANIFESTACION:
        return "final_muerte_manifestacion"
    return "final_muerte"


def _opcion_extra_disponible(estado: EstadoJugador, nodo) -> bool:
    return (
        not nodo.es_final
        and nodo.destino_cansancio is not None
        and estado.turno >= _limite_cansancio(estado)
    )


# Cuántas opciones tácticas se muestran como máximo por escena. Varios hubs
# (esquina_barrio, semana_presidentes_1/2) definen muchas más ubicaciones
# posibles de las que tiene sentido mostrar todas juntas — se resuelve
# sampleando un subconjunto distinto en cada visita, no recortando el
# contenido de game/story.py. Ver _generar_orden_opciones.
MAX_OPCIONES_VISIBLES = 5


def _camino_permite(estado: EstadoJugador, requiere_camino: str) -> bool:
    """Un jugador comprometido con el camino contrario (ver
    game/state.py:resumen_camino) deja de ver los sidequests del otro lado.
    El camino ambivalente (el del medio) siempre ve los dos: es el único que
    surfea ambos lados de la coyuntura."""
    camino_actual = resumen_camino(estado.alineacion)
    if requiere_camino == "bueno" and camino_actual == "fuera de la ley":
        return False
    if requiere_camino == "malo" and camino_actual == "dentro de la ley":
        return False
    return True


def _opciones_disponibles(estado: EstadoJugador, nodo) -> List[int]:
    """Índices reales de las opciones que el jugador PUEDE elegir ahora mismo
    (según requiere_flag/requiere_item/excluye_flag), no todas las definidas
    en el nodo. Antes se mostraban todas y recién al elegir una se le avisaba
    al jugador "no podés hacer eso" — ahora directamente no se ofrecen."""
    disponibles = []
    for i, opcion in enumerate(nodo.opciones):
        if opcion.requiere_flag and not estado.tiene_flag(opcion.requiere_flag):
            continue
        if opcion.requiere_item and not estado.tiene_item(opcion.requiere_item):
            continue
        if opcion.excluye_flag and estado.tiene_flag(opcion.excluye_flag):
            continue
        if opcion.requiere_salud_maxima is not None and estado.salud > opcion.requiere_salud_maxima:
            continue
        if opcion.requiere_camino and not _camino_permite(estado, opcion.requiere_camino):
            continue
        disponibles.append(i)
    return disponibles or list(range(len(nodo.opciones)))


def _generar_orden_opciones(estado: EstadoJugador, nodo) -> List[int]:
    disponibles = _opciones_disponibles(estado, nodo)
    if len(disponibles) > MAX_OPCIONES_VISIBLES:
        return random.sample(disponibles, MAX_OPCIONES_VISIBLES)
    random.shuffle(disponibles)
    return disponibles


def _chequear_vencimiento_comedor(estado: EstadoJugador) -> None:
    """Si el mandado de Doña Rosa lleva demasiados turnos sin resolverse, se
    da por perdido: no se puede dejar "colgado" para siempre sin costo."""
    if estado.turno_mision_comedor is None:
        return
    if estado.turno - estado.turno_mision_comedor < TURNO_LIMITE_COMEDOR:
        return
    estado.flags.discard("mision_comedor_activa")
    estado.flags.add("mision_comedor_fallida")
    estado.reputacion_barrial -= 5
    estado.turno_mision_comedor = None


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
    estado.zona_gba = detectar_zona_gba(estado.barrio_inicial)
    estado.inventario = list(INVENTARIO_INICIAL)
    estado.dinero = Dinero(pesos=15, patacones=20, lecops=10)
    nodo_inicial = NODO_INICIAL_POR_CATEGORIA.get(categoria, "inicio_generico")
    _entrar_nodo(estado, nodo_inicial)
    return estado


def elegir_final(estado: EstadoJugador) -> str:
    """Decide a qué final corresponde llegar según alineación/flags/reputación."""
    if not estado.vivo:
        return _destino_muerte(estado)

    # El camino "referente piquetero" (ganar habiendo hecho solo cosas fuera
    # de la ley) exige una combinación muy específica conseguida en
    # game/story.py (piquetero_violento_1 y 2): haber tirado la molotov en
    # el primer tramo, haber zafado de la cana o resistido hasta el final en
    # el segundo, y que la alineación haya quedado bien negativa — no es
    # alcanzable por casualidad ni por una sola decisión aislada.
    if (
        estado.tiene_flag("tiraste_molotov")
        and (estado.tiene_flag("zafaste_de_la_cana") or estado.tiene_flag("resististe_hasta_el_final"))
        and estado.alineacion <= -30
    ):
        return "final_referente_piquetero"

    categoria = estado.objetivo_categoria
    objetivo_logrado = (
        (categoria == "plata" and estado.tiene_flag("objetivo_cumplido_plata"))
        or (categoria == "familiar" and estado.tiene_flag("buscando_familiar") and estado.reputacion_barrial >= 5)
        or (categoria == "negocio" and estado.tiene_flag("defendiste_comercio"))
    )
    if objetivo_logrado:
        return "final_objetivo_cumplido"

    plata_total = estado.dinero.pesos + estado.dinero.patacones + estado.dinero.lecops

    if estado.alineacion <= -35:
        # Camino fuera de la ley sin haber armado la combinación especial:
        # es el que más fácil termina mal. Si encima quedaste sin un mango,
        # terminás de cartonero; si no, sobrevivís solo, a los ponchazos.
        if plata_total < 15 and estado.reputacion_barrial < 5:
            return "final_cartonero"
        return "final_solitario"

    if estado.alineacion >= 35 and estado.reputacion_barrial >= 15:
        return "final_comunidad"

    return "final_solitario"


def _entrar_nodo(estado: EstadoJugador, nodo_id: str) -> None:
    if nodo_id == "final_decision":
        nodo_id = elegir_final(estado)
    if nodo_id == "volver_al_hub":
        nodo_id = HUB_POR_CAPITULO.get(estado.capitulo, "esquina_barrio")
    if nodo_id == "avanzar_capitulo":
        # Sentinel reutilizable para sidequests que hacen "perder un día":
        # salta directo al hub del capítulo siguiente. En los capítulos 1 y
        # 2 (que comparten hub) esto no mueve de nodo — ahí el costo real de
        # la sidequest son sus propios salud_delta/dinero_delta, no el
        # salto — pero a partir del capítulo 3 cada capítulo tiene su propio
        # hub y el salto sí es un adelanto real de la historia.
        siguiente_capitulo = min(estado.capitulo + 1, 7)
        nodo_id = HUB_POR_CAPITULO.get(siguiente_capitulo, "esquina_barrio")

    if (
        nodo_id in HUB_POR_CAPITULO.values()
        and estado.turno > 0
        and estado.nodo_actual not in NODOS_EVENTO_AMBIENTAL
        and random.random() < PROB_EVENTO_AMBIENTAL
    ):
        categoria = random.choice(CATEGORIAS_EVENTO_AMBIENTAL)
        if categoria == "demora_transporte":
            nodo_id = DEMORA_TRANSPORTE_POR_ZONA.get(estado.zona_gba, "demora_transporte_generico")
        else:
            nodo_id = categoria

    nodo = story.obtener_nodo(nodo_id)
    estado.nodo_actual = nodo_id
    estado.ubicacion = nodo.ubicacion
    estado.lugares_visitados.add(nodo.ubicacion)
    estado.turno += 1
    if nodo.capitulo is not None:
        estado.capitulo = nodo.capitulo
    _chequear_vencimiento_comedor(estado)
    estado.orden_opciones = _generar_orden_opciones(estado, nodo) if not nodo.es_final else []

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

    if nodo.es_final:
        opciones_texto: List[str] = []
    else:
        orden = estado.orden_opciones or list(range(len(nodo.opciones)))
        opciones_texto = [nodo.opciones[i].texto for i in orden if i < len(nodo.opciones)]
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
            "dia": estado.etiqueta_capitulo(),
            "mision": estado.objetivo,
            "camino": resumen_camino(estado.alineacion),
        },
        "estadisticas": estado.generar_estadisticas(nodo.final_tipo) if nodo.es_final else None,
        "mensaje_error": None,
        "mensaje_efecto": None,
        "mensaje_libre": None,
    }


def _prob_efectiva(estado: EstadoJugador, opcion: "story.Opcion") -> float:
    """Ajusta `opcion.prob_alt` según qué tiene encima o a favor el jugador en
    el momento de elegir la opción (documento en regla, plata, mercadería
    robada, reputación barrial), sin tener que duplicar nodos por cada
    combinación posible. Ver el comentario sobre estos campos en story.py."""
    prob = opcion.prob_alt

    if opcion.item_favorable and estado.tiene_item(opcion.item_favorable):
        prob -= opcion.bonus_item_favorable
    if opcion.item_desfavorable and estado.tiene_item(opcion.item_desfavorable):
        prob += opcion.penalizacion_item_desfavorable
    if opcion.condicion_desfavorable and (
        opcion.condicion_desfavorable in estado.flags
        or opcion.condicion_desfavorable in estado.estados
    ):
        prob += opcion.penalizacion_condicion_desfavorable
    if (
        opcion.reputacion_minima_favorable is not None
        and estado.reputacion_barrial >= opcion.reputacion_minima_favorable
    ):
        prob -= opcion.bonus_reputacion_favorable
    if (
        opcion.pesos_minimos_favorable is not None
        and estado.dinero.pesos >= opcion.pesos_minimos_favorable
    ):
        prob -= opcion.bonus_pesos_favorable

    return max(0.0, min(1.0, prob))


def _bonus_salud_reputacion(estado: EstadoJugador, opcion: "story.Opcion") -> int:
    """Si la reputación barrial alcanza el umbral de la opción (un vecino o
    testigo interviene), suma el bonus de salud definido en la opción."""
    if (
        opcion.reputacion_minima_favorable is not None
        and estado.reputacion_barrial >= opcion.reputacion_minima_favorable
    ):
        return opcion.bonus_salud_reputacion
    return 0


def elegir_opcion(estado: EstadoJugador, indice_humano: int) -> Dict[str, Any]:
    """Aplica la opción táctica número `indice_humano` (1-based, en el orden
    ya mezclado que se le mostró al jugador) y avanza la historia."""
    nodo = story.obtener_nodo(estado.nodo_actual)

    if nodo.es_final:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "La partida ya terminó. Empezá una nueva para seguir jugando."
        return vista

    idx_mostrado = indice_humano - 1
    orden = estado.orden_opciones or list(range(len(nodo.opciones)))

    if _opcion_extra_disponible(estado, nodo) and idx_mostrado == len(orden):
        estado.salud += random.randint(-3, 3)
        estado.salud_clamp()
        destino = _destino_muerte(estado) if not estado.vivo else nodo.destino_cansancio
        _entrar_nodo(estado, destino)
        return vista_actual(estado)

    if idx_mostrado < 0 or idx_mostrado >= len(orden):
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Esa opción no existe. Elegí un número de la lista o escribí una acción libre."
        return vista

    opcion = nodo.opciones[orden[idx_mostrado]]

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
    if opcion.requiere_salud_maxima is not None and estado.salud > opcion.requiere_salud_maxima:
        vista = vista_actual(estado)
        vista["mensaje_error"] = "No lo necesitás por ahora."
        return vista
    if opcion.requiere_camino and not _camino_permite(estado, opcion.requiere_camino):
        vista = vista_actual(estado)
        vista["mensaje_error"] = "Ya no es algo que harías, con el camino que elegiste."
        return vista

    alineacion_antes = estado.alineacion

    if opcion.salud_delta != (0, 0):
        estado.salud += random.randint(*opcion.salud_delta)
    estado.reputacion_barrial += opcion.reputacion_delta
    estado.alineacion = max(-100, min(100, estado.alineacion + opcion.alineacion_delta))
    estado.dinero.aplicar(opcion.dinero_delta)
    if opcion.establece_categoria:
        estado.objetivo_categoria = opcion.establece_categoria
    estado.flags.update(opcion.flags_add)
    for f in opcion.flags_quitar:
        estado.flags.discard(f)
    if "mision_comedor_activa" in opcion.flags_add:
        estado.turno_mision_comedor = estado.turno
    if "encargo_encontrado" in opcion.flags_add or "mision_comedor_completa" in opcion.flags_add:
        estado.turno_mision_comedor = None
    for item in opcion.items_add:
        estado.agregar_item(item)
    for item in opcion.items_quitar:
        estado.quitar_item(item)
    estado.estados.update(opcion.estados_add)
    for e in opcion.estados_quitar:
        estado.estados.discard(e)

    mensaje_robo = ""
    if opcion.roba_item_aleatorio and estado.inventario:
        item_robado = random.choice(estado.inventario)
        estado.quitar_item(item_robado)
        mensaje_robo = f" Te afanaron algo en el quilombo: {item_robado}."
        if item_robado == "documento de identidad":
            estado.flags.add("sin_documento")

    estado.salud += _bonus_salud_reputacion(estado, opcion)
    estado.salud_clamp()

    if not estado.vivo:
        destino = _destino_muerte(estado)
    elif opcion.destino_alt and random.random() < _prob_efectiva(estado, opcion):
        destino = opcion.destino_alt
    else:
        destino = opcion.destino

    _entrar_nodo(estado, destino)
    vista = vista_actual(estado)
    aviso_camino = mensaje_cambio_camino(alineacion_antes, estado.alineacion)
    if opcion.mensaje_efecto or mensaje_robo or aviso_camino:
        partes = [opcion.mensaje_efecto.strip(), mensaje_robo.strip(), aviso_camino or ""]
        vista["mensaje_efecto"] = " ".join(p for p in partes if p)

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
    """Procesa la opción "escribí tu propia acción"."""
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
        destino = _destino_muerte(estado)
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
