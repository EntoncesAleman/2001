"""Grafo narrativo del RPG "2001: Odisea en Buenos Aires".

Cada `Nodo` es una escena. Cada `Opcion` es una acción táctica que lleva a
otro nodo y puede tener efectos mecánicos (salud, dinero, reputación,
inventario, flags de historia). No hay "armadura de guion": los rangos de
salud son aleatorios (`random.randint`) y si la salud llega a 0 el jugador
muere, sin importar en qué nodo esté.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Opcion:
    texto: str
    destino: str

    salud_delta: Tuple[int, int] = (0, 0)
    dinero_delta: Dict[str, int] = field(default_factory=dict)
    reputacion_delta: int = 0
    alineacion_delta: int = 0

    flags_add: Tuple[str, ...] = ()
    flags_quitar: Tuple[str, ...] = ()
    items_add: Tuple[str, ...] = ()
    items_quitar: Tuple[str, ...] = ()
    estados_add: Tuple[str, ...] = ()
    estados_quitar: Tuple[str, ...] = ()
    roba_item_aleatorio: bool = False

    requiere_flag: Optional[str] = None
    requiere_item: Optional[str] = None
    excluye_flag: Optional[str] = None
    # Solo se ofrece si la salud actual es <= a este valor (ej: la opción de
    # ir al hospital no tiene sentido mostrarla si estás en buen estado).
    requiere_salud_maxima: Optional[int] = None

    # Fija/sobrescribe estado.objetivo_categoria (una de las claves de
    # CATEGORIAS_OBJETIVO en game/state.py: "plata", "familiar", "negocio",
    # "generico"). Se usa en el nodo "elegir_mision": la categoría detectada
    # automáticamente del texto libre del objetivo solo decide qué variante
    # de apertura (inicio_plata/familiar/negocio/generico) ve el jugador;
    # la elección explícita acá es la que de verdad cuenta para
    # engine.py:elegir_final.
    establece_categoria: Optional[str] = None

    # Marca esta opción como propia de un camino ("bueno" o "malo"): un
    # jugador ya comprometido con el camino contrario (alineación <= -35 o
    # >= 35, ver game/state.py:resumen_camino) deja de verla — así el camino
    # bueno y el malo no ofrecen los mismos sidequests. El camino ambivalente
    # (el del medio) sigue viendo ambos: es el único que "surfea" los dos
    # lados. No confundir con alineacion_delta (el efecto de elegirla): esto
    # es sobre si se OFRECE, no sobre qué hace.
    requiere_camino: Optional[str] = None

    destino_alt: Optional[str] = None
    prob_alt: float = 0.0

    # --- Modificadores contextuales -----------------------------------
    # Ajustan la probabilidad efectiva de que dispare destino_alt (o, en el
    # caso de la reputación, la salud perdida) según qué tiene encima el
    # jugador en el momento de elegir la opción — sin tener que duplicar
    # nodos por cada combinación posible. Ver game/engine.py:_prob_efectiva.
    item_favorable: Optional[str] = None
    bonus_item_favorable: float = 0.15
    item_desfavorable: Optional[str] = None
    penalizacion_item_desfavorable: float = 0.2
    # Se chequea contra flags Y estados a la vez (ej: "sin_documento" es un
    # flag; "herido en la pierna" es un estado — a los efectos de esto da lo
    # mismo, ambos son "algo que te complica la situación").
    condicion_desfavorable: Optional[str] = None
    penalizacion_condicion_desfavorable: float = 0.2
    reputacion_minima_favorable: Optional[int] = None
    bonus_reputacion_favorable: float = 0.1
    bonus_salud_reputacion: int = 0
    pesos_minimos_favorable: Optional[int] = None
    bonus_pesos_favorable: float = 0.15

    mensaje_efecto: str = ""


# Probabilidades de referencia para marcar una opción como "delictiva":
# siempre que un personaje hace algo ilegal, tiene que existir la chance de
# que la policía lo esté persiguiendo poco después (destino_alt="persecucion").
RIESGO_BAJO = 0.15
RIESGO_MEDIO = 0.3
RIESGO_ALTO = 0.5


@dataclass(frozen=True)
class Nodo:
    id: str
    ubicacion: str
    narracion: str
    dialogos: Tuple[Tuple[str, str], ...] = ()
    imagen_en: Optional[str] = None
    opciones: Tuple[Opcion, ...] = ()
    destino_libre: Optional[str] = None
    salud_entrada: Tuple[int, int] = (0, 0)
    estados_entrada: Tuple[str, ...] = ()
    es_final: bool = False
    final_tipo: Optional[str] = None
    # Si está seteado, este nodo es un "hub" de capítulo: a partir de
    # _limite_cansancio() (game/engine.py, varía según la zona del GBA de la
    # que sale el personaje) aparece una opción extra para cerrar la escena y
    # avanzar directo a este destino, sin importar qué más haya para
    # explorar acá. Nodos de paso (no-hub) lo dejan en None.
    destino_cansancio: Optional[str] = None
    # Capítulo de la campaña al que pertenece (1 = días previos, 2 = noche
    # del 19, 3 = el día del estallido, 4-6 = la semana de los presidentes,
    # 7 = cierre). None = no cambia el capítulo actual al entrar (nodos de
    # servicio como el hospital o el trueque, reusados en varios capítulos).
    capitulo: Optional[int] = None


NODOS: Dict[str, Nodo] = {}


def _registrar(nodo: Nodo) -> None:
    NODOS[nodo.id] = nodo


# ---------------------------------------------------------------------------
# 0. Aperturas (varían según el objetivo elegido al crear el personaje;
#    todas convergen a "esquina_barrio" en un solo paso — la misma aventura
#    puede arrancar de formas distintas y llegar a los mismos lugares).
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="inicio_plata",
    ubicacion="Tu casa, temprano a la mañana",
    narracion=(
        "Contás las últimas monedas de 25 sobre la mesa de la cocina, al lado "
        "de la libreta del banco que ya casi no sirve de nada: los números "
        "que dice y la plata real que existe hace rato que dejaron de ser lo "
        "mismo. Tenés que salir a resolver esto como sea."
    ),
    opciones=(
        Opcion(texto="Salir para el barrio a ver qué se puede hacer", destino="elegir_mision"),
    ),
    destino_libre="elegir_mision",
    capitulo=1,
))

_registrar(Nodo(
    id="inicio_familiar",
    ubicacion="Tu casa, temprano a la mañana",
    narracion=(
        "Hace días que no sabés nada. El teléfono de línea corta y vuelve "
        "según el humor del día, y la última vez que hablaste todo sonaba "
        "raro, apurado. Te calzás las zapatillas: hoy vas a tratar de "
        "averiguar algo más."
    ),
    opciones=(
        Opcion(texto="Salir para el barrio a preguntar y buscar noticias", destino="elegir_mision"),
    ),
    destino_libre="elegir_mision",
    capitulo=1,
))

_registrar(Nodo(
    id="inicio_negocio",
    ubicacion="Tu casa, temprano a la mañana",
    narracion=(
        "Antes de salir mirás una vez más los números del changuito: si esto "
        "sigue así, no llegás a fin de mes. El negocio que tanto costó "
        "levantar pende de un hilo, igual que todo lo demás en este país "
        "esta semana."
    ),
    opciones=(
        Opcion(texto="Salir para el barrio a ver cómo sigue el día", destino="elegir_mision"),
    ),
    destino_libre="elegir_mision",
    capitulo=1,
))

_registrar(Nodo(
    id="inicio_generico",
    ubicacion="Tu casa, temprano a la mañana",
    narracion=(
        "Prendés la radio mientras te tomás un mate lavado —el bueno hace "
        "rato que no alcanza para todo el mes—. El locutor repite, cansado, "
        "las mismas malas noticias de siempre con otras palabras. Es hora "
        "de salir."
    ),
    opciones=(
        Opcion(texto="Salir a la calle a ver cómo sigue el día", destino="elegir_mision"),
    ),
    destino_libre="elegir_mision",
    capitulo=1,
))

_registrar(Nodo(
    id="elegir_mision",
    ubicacion="En la puerta de tu casa, a punto de salir",
    narracion=(
        "Antes de cruzar la puerta te quedás un segundo pensando bien qué es "
        "lo que tenés que resolver hoy. No vas a poder ocuparte de todo a la "
        "vez: elegí tu prioridad, porque de esto depende buena parte de lo "
        "que te pase de acá en adelante."
    ),
    opciones=(
        Opcion(
            texto="Prioridad: pelear por tus ahorros en el banco",
            destino="esquina_barrio",
            establece_categoria="plata",
        ),
        Opcion(
            texto="Prioridad: buscar noticias de un familiar del que no sabés nada",
            destino="esquina_barrio",
            establece_categoria="familiar",
        ),
        Opcion(
            texto="Prioridad: proteger tu changa, tu local o tu comercio",
            destino="esquina_barrio",
            establece_categoria="negocio",
        ),
        Opcion(
            texto="Prioridad: ninguna en particular, ver cómo se da el día y arreglártelas",
            destino="esquina_barrio",
            establece_categoria="generico",
        ),
    ),
    destino_libre="esquina_barrio",
))


# ---------------------------------------------------------------------------
# 1. Punto de partida
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="esquina_barrio",
    ubicacion="Esquina de tu barrio, Gran Buenos Aires",
    narracion=(
        "El sol de diciembre pega fuerte sobre el asfalto rajado. A dos cuadras "
        "se escucha, apagado pero constante, el repiqueteo de cacerolas: alguien "
        "empezó temprano hoy. En la persiana medio baja del kiosco de la esquina "
        "hay un cartel de fibrón: \"NO SE ACEPTAN PATACONES NI LECOPS - SOLO PESOS\". "
        "Un colectivo pasa con el boletero automático haciendo un ruido metálico "
        "raro, tragando las monedas de 25 que ya casi no quedan en la calle. "
        "Tenés que decidir para dónde tirar."
    ),
    dialogos=(
        ("Vecina de la esquina", "¿Vos también vas para el banco? Yo hace tres días que vengo y nada, che."),
    ),
    imagen_en=(
        "a middle-class Buenos Aires suburban street corner at midday in December 2001, "
        "a half-closed kiosk with a handwritten cardboard sign, a colectivo bus passing by, "
        "a person standing at the corner looking uncertain, distant smoke on the horizon"
    ),
    opciones=(
        Opcion(texto="Ir para el banco a intentar sacar algo de guita", destino="banco_fila"),
        Opcion(
            texto="Acercarte a la asamblea que se está armando en la placita",
            destino="asamblea_barrial",
            requiere_camino="bueno",
        ),
        Opcion(texto="Ir al club de trueque a ver qué conseguís para comer", destino="club_trueque"),
        Opcion(texto="Pasar por el cibercafé a ver si hay noticias o mensajes", destino="cibercafe"),
        Opcion(texto="Ir hasta el piquete que cortó la ruta de acceso", destino="piquete"),
        Opcion(
            texto="Sumarte a cortar una ruta en otro barrio, con gente que no conocés de nada",
            destino="piquete_ruta_ajena",
            alineacion_delta=-6,
            requiere_camino="malo",
        ),
        Opcion(texto="Agarrar tus cosas e intentar irte del Conurbano/CABA ahora mismo", destino="control_ruta"),
        Opcion(texto="Pasar por el comedor del barrio a ver si hay algo para comer", destino="comedor"),
        Opcion(texto="Ir hasta el hospital de guardia si te sentís mal", destino="hospital", requiere_salud_maxima=80),
        Opcion(
            texto="Comer algo de lo que tenés en la bolsa de mercadería",
            destino="volver_al_hub",
            requiere_item="bolsa de mercadería",
            items_quitar=("bolsa de mercadería",),
            salud_delta=(10, 20),
            mensaje_efecto="No es gran cosa, pero algo en el estómago cambia todo.",
        ),
    ),
    destino_libre="volver_al_hub",
    destino_cansancio="cacerolazo_19",
    capitulo=1,
))


# ---------------------------------------------------------------------------
# 2. El Corralito
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="banco_fila",
    ubicacion="Fila del banco, sucursal con las persianas blindadas",
    narracion=(
        "La fila da vuelta la esquina. Hay señoras con silla de plástico traída "
        "de la casa, un tipo de traje que ya se aflojó la corbata hace rato, un "
        "pibe escuchando el walkman para hacer tiempo. Cada tanto alguien golpea "
        "la reja y putea al aire, porque el cajero de adentro tampoco tiene la "
        "culpa. Un cartel de cadena dice: \"POR RAZONES DE SEGURIDAD, EXTRACCIONES "
        "LIMITADAS\". El corralito, le dicen. Tu plata está ahí adentro, blindada, "
        "y vos afuera."
    ),
    imagen_en=(
        "a long line of people waiting outside a bank with metal security "
        "shutters partially down, people carrying plastic chairs from home, a "
        "handwritten sign about withdrawal limits, tense crowded sidewalk scene"
    ),
    dialogos=(
        ("Señor de traje", "Yo laburé treinta años para esto, pibe. Treinta años."),
    ),
    opciones=(
        Opcion(texto="Esperar tu turno con paciencia, como todos", destino="banco_espera",
               salud_delta=(-4, -1)),
        Opcion(texto="Acercarte al guardia de la puerta a ver si por izquierda se puede algo", destino="banco_soborno",
               requiere_item=None),
        Opcion(texto="Sumarte a la gente que empieza a golpear las rejas y putear", destino="banco_protesta"),
        Opcion(texto="Rajar de la fila, esto no va a ningún lado", destino="volver_al_hub"),
    ),
    destino_libre="banco_fila",
))

_registrar(Nodo(
    id="banco_espera",
    ubicacion="Fila del banco",
    narracion=(
        "Pasan las horas. El sol te cocina la nuca. De golpe, un empleado sale y "
        "cuelga un cartel nuevo: \"NO HAY MÁS EFECTIVO POR HOY\". Un segundo de "
        "silencio. Después, el estallido: gritos, insultos, alguien llora, otro "
        "se ríe con una risa fea, de bronca. \"Que se vayan todos\", grita una "
        "voz sola, y enseguida la repiten diez más."
    ),
    salud_entrada=(-3, -1),
    opciones=(
        Opcion(texto="Sumarte al reclamo, gritar con los demás", destino="banco_protesta",
               flags_add=("vivio_corralito",)),
            Opcion(texto="Rajar frustrado hacia la asamblea del barrio", destino="asamblea_barrial",
               flags_add=("vivio_corralito",)),
        Opcion(texto="Aceptar que hoy no hay nada y probar suerte en el trueque", destino="club_trueque",
               flags_add=("vivio_corralito",)),
    ),
    destino_libre="banco_protesta",
))

_registrar(Nodo(
    id="banco_soborno",
    ubicacion="Puerta del banco",
    narracion=(
        "Te acercás al guardia, un tipo grandote con cara de que ya escuchó todas "
        "las excusas del mundo. Le susurrás si \"hay alguna forma\" de agilizar "
        "las cosas. Te mira de arriba abajo, calculando cuánto tenés y cuánto "
        "riesgo vale la pena correr por vos."
    ),
    opciones=(
        Opcion(
            texto="Ofrecerle unos pesos para que te deje pasar",
            destino="banco_protesta",
            destino_alt="banco_adentro",
            prob_alt=0.4,
            dinero_delta={"pesos": -20},
            reputacion_delta=-5,
            alineacion_delta=-5,
            mensaje_efecto="El guardia se guarda los billetes en el bolsillo del chaleco sin mirarte a los ojos.",
        ),
        Opcion(texto="Arrepentirte y volver a la fila como todo el mundo", destino="banco_fila"),
    ),
    destino_libre="banco_fila",
))

_registrar(Nodo(
    id="banco_adentro",
    ubicacion="Adentro del banco",
    narracion=(
        "El guardia te hace una seña casi imperceptible y te cuela por una "
        "puerta lateral. Adentro el aire acondicionado es otro mundo. Un cajero "
        "cansado, sin ganas de discutir con nadie más hoy, te cuenta unos "
        "billetes de verdad, pesos de los de antes, y te los pasa por debajo del "
        "mostrador. \"Andate rápido y no digas nada\", te dice, sin levantar la "
        "vista. Al salir, algunos en la fila te miran raro: te vieron entrar por "
        "donde no era."
    ),
    opciones=(
        Opcion(texto="Salir rápido y perderte entre la gente", destino="volver_al_hub",
               dinero_delta={"pesos": 60}, flags_add=("objetivo_cumplido_plata",)),
        Opcion(texto="Ir directo al club de trueque a hacer rendir esa plata", destino="club_trueque",
               dinero_delta={"pesos": 60}, flags_add=("objetivo_cumplido_plata",)),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="banco_protesta",
    ubicacion="Frente al banco, la fila ya es otra cosa",
    narracion=(
        "La fila dejó de ser fila. Ahora es una masa de gente golpeando las "
        "persianas metálicas con las manos, con palos, alguno ya sacó una "
        "cacerola de la bolsa del súper y la usa de tambor. \"¡LADRONES! ¡QUE SE "
        "VAYAN TODOS!\" El estruendo se contesta desde otras cuadras: en toda la "
        "ciudad está pasando lo mismo, al mismo tiempo, como si todos se hubieran "
        "puesto de acuerdo sin hablar. A lo lejos, sirenas."
    ),
    imagen_en=(
        "an angry crowd of people banging pots and fists against a bank's steel security "
        "shutters in Buenos Aires in December 2001, some improvised percussion with kitchen pans, "
        "riot police vehicles approaching in the distant background, dusk light"
    ),
    opciones=(
        Opcion(texto="Quedarte al frente, gritando con los demás", destino="represion"),
        Opcion(
            texto="Escabullirte antes de que esto se ponga peor",
            destino="volver_al_hub",
            destino_alt="represion",
            prob_alt=0.3,
        ),
        Opcion(
            texto="Proponerle a la gente cercana organizarse en asamblea en vez de gritar solos",
            destino="asamblea_barrial",
            reputacion_delta=5,
            alineacion_delta=5,
        ),
    ),
    destino_libre="represion",
))


# ---------------------------------------------------------------------------
# 3. Represión / cacerolazo (clímax de acción)
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="represion",
    ubicacion="Calle tomada, en medio de la represión",
    narracion=(
        "Los carros hidrantes avanzan de a poco, empujando a la gente contra las "
        "veredas. Un estruendo seco —gas lacrimógeno— y el aire se pone espeso, "
        "te arden los ojos como si te los estuvieran lavando con lavandina. La "
        "gente corre en todas direcciones, alguien grita que tiraron con balas "
        "de goma, más atrás alguien más grita que no eran de goma. Un vecino "
        "mayor se cae al lado tuyo y no se levanta solo."
    ),
    imagen_en=(
        "chaotic riot scene, anti-riot police firing tear gas at a fleeing crowd in a "
        "Buenos Aires avenue at dusk in December 2001, smoke, fire from a barricade, "
        "dramatic and grim action scene"
    ),
    opciones=(
        Opcion(
            texto="Correr a los gritos para salvarte vos primero",
            destino="volver_al_hub",
            salud_delta=(-25, -8),
            estados_add=("tos por gases",),
            reputacion_minima_favorable=15,
            bonus_salud_reputacion=10,
        ),
        Opcion(
            texto="Parar a levantar al vecino caído aunque te arriesgues",
            destino="volver_al_hub",
            destino_alt="represion_herido",
            prob_alt=0.45,
            salud_delta=(-15, -5),
            reputacion_delta=12,
            flags_add=("ayudaste_en_represion",),
            estados_add=("tos por gases",),
            reputacion_minima_favorable=15,
            bonus_reputacion_favorable=0.15,
            bonus_salud_reputacion=8,
        ),
        Opcion(
            texto="Plantarte de espaldas a una pared y esperar a que pase la corrida",
            destino="volver_al_hub",
            salud_delta=(-35, -10),
            estados_add=("tos por gases", "agitado"),
            reputacion_minima_favorable=15,
            bonus_salud_reputacion=12,
        ),
    ),
    destino_libre="represion_herido",
))

_registrar(Nodo(
    id="represion_herido",
    ubicacion="Vereda, en medio de la corrida",
    narracion=(
        "Algo te pega fuerte en la pierna —después vas a saber que fue una bala "
        "de goma, por suerte, no de plomo— y te desplomás un segundo antes de "
        "poder seguir arrastrándote hacia una entrada de edificio. El dolor es "
        "un fuego blanco. Un desconocido te agarra del brazo y te mete adentro "
        "justo antes de que pase la tanqueta."
    ),
    salud_entrada=(-20, -10),
    estados_entrada=("herido en la pierna",),
    opciones=(
        Opcion(texto="Agradecer y quedarte ahí escondido hasta que amaine", destino="volver_al_hub",
               reputacion_delta=3),
        Opcion(texto="Salir igual, apenas termine la corrida, a buscar a los tuyos", destino="volver_al_hub",
               salud_delta=(-10, -3)),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 4. Asamblea barrial
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="asamblea_barrial",
    ubicacion="Placita del barrio, asamblea vecinal",
    narracion=(
        "En la placita se armó una ronda de sillas de todos los colores, "
        "traídas de las casas de alrededor. Alguien anotó un orden del día en "
        "un cuaderno Rivadavia. Se discute de todo: la olla popular de mañana, "
        "quién tiene una radio para avisar si vuelve la cana, cómo organizar una "
        "barricada si hace falta. Hay bronca, pero también algo parecido a la "
        "esperanza: la sensación de que, si nadie más se hace cargo, al menos "
        "se tienen entre ustedes."
    ),
    imagen_en=(
        "a neighborhood assembly in a small plaza at night, a circle of "
        "mismatched chairs brought from nearby houses, a diverse group of "
        "neighbors in animated discussion, someone taking notes in a notebook"
    ),
    dialogos=(
        ("Vecino de la asamblea", "Acá nadie te va a solucionar la vida, pero al menos no estás solo, ¿entendés?"),
    ),
    opciones=(
        Opcion(texto="Ofrecerte para ayudar a organizar la olla popular de mañana", destino="asamblea_propuesta",
               reputacion_delta=8),
        Opcion(texto="Escuchar un rato y sumar tu opinión sobre el banco/la fila", destino="asamblea_propuesta",
               reputacion_delta=4),
        Opcion(texto="Preguntar si alguien sabe algo de gente perdida en algún saqueo", destino="cibercafe_noticia",
               requiere_flag=None),
        Opcion(texto="Sumarte a un corte de ruta que están organizando entre varios", destino="piquete"),
        Opcion(texto="Retirarte, esto no es lo tuyo", destino="volver_al_hub"),
    ),
    destino_libre="asamblea_propuesta",
))

_registrar(Nodo(
    id="asamblea_propuesta",
    ubicacion="Placita del barrio, asamblea vecinal",
    narracion=(
        "Te metés de lleno. Entre todos arman una lista de lo que hay: harina "
        "acá, un poco de aceite allá, alguien ofrece la cocina de su casa. Nadie "
        "tiene demasiado, pero juntando de a poco alcanza. Te anotan en la lista "
        "de \"gente de confianza\" para la olla de mañana. Por primera vez en "
        "el día, algo se siente resuelto, aunque sea chiquito."
    ),
    salud_entrada=(2, 6),
    opciones=(
        Opcion(texto="Ir para el club de trueque a conseguir algo para aportar", destino="club_trueque",
               reputacion_delta=3),
        Opcion(texto="Volver a tu casa a descansar, mañana es otro día largo", destino="volver_al_hub",
               salud_delta=(5, 12)),
        Opcion(texto="Quedarte a dormir en la placita, cuidando entre todos por si vuelve la cana", destino="volver_al_hub",
               flags_add=("noche_en_asamblea",), reputacion_delta=5, alineacion_delta=4),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 5. Club de trueque
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="club_trueque",
    ubicacion="Club de trueque del barrio, un galpón con mesas de feria",
    narracion=(
        "El galpón huele a humedad y a pan casero. En las mesas hay de todo: "
        "ropa doblada prolijamente, herramientas oxidadas pero servibles, "
        "dulce casero en frascos de mayonesa reciclados, hasta cortes de pelo "
        "\"a cambio de créditos\". Nadie te pide pesos ni Patacones acá: es todo "
        "créditos de trueque, o cambio directo. Una señora con delantal maneja "
        "una lista en un cuaderno como si fuera el Banco Central del barrio."
    ),
    imagen_en=(
        "the inside of a bustling barter club set up in a warehouse, market "
        "stalls with folded clothes, tools, and homemade preserves, a crowd of "
        "neighbors trading goods, a woman with an apron keeping a ledger"
    ),
    dialogos=(
        ("Coordinadora del club", "Acá nadie te va a garcar con la cotización, che. Un crédito es un crédito."),
    ),
    opciones=(
        Opcion(texto="Cambiar parte de tus Patacones/Lecops por créditos de trueque", destino="club_trueque_intercambio",
               dinero_delta={"patacones": 0}),
        Opcion(texto="Ofrecer algo de tu inventario a cambio de comida", destino="club_trueque_intercambio"),
        Opcion(texto="Quedarte charlando para enterarte de rumores del barrio", destino="club_trueque_intercambio",
               reputacion_delta=2),
        Opcion(
            texto="Preguntar bajito si alguien conoce a un reducidor para objetos... especiales",
            destino="camino_mercado_negro",
            alineacion_delta=-5,
            requiere_camino="malo",
        ),
        Opcion(texto="Irte, esto no te resuelve nada hoy", destino="volver_al_hub"),
    ),
    destino_libre="club_trueque_intercambio",
))

_registrar(Nodo(
    id="club_trueque_intercambio",
    ubicacion="Club de trueque del barrio",
    narracion=(
        "Terminás de acomodar el trato: entregás lo que tenés de más y te "
        "volvés con una bolsa de mercadería —fideos, un poco de dulce, algo de "
        "verdura— y un puñado de créditos para la próxima. La coordinadora te "
        "anota en el cuaderno y te dice que vuelvas cuando quieras, que \"acá "
        "la única condición es no garcar a nadie\"."
    ),
    opciones=(
        Opcion(texto="Volver a tu barrio con la mercadería conseguida", destino="volver_al_hub",
               dinero_delta={"creditos_trueque": 10, "patacones": -5}, items_add=("bolsa de mercadería",)),
        Opcion(texto="Pasar por la asamblea a aportar parte de lo conseguido", destino="asamblea_barrial",
               dinero_delta={"creditos_trueque": 5}, items_add=("bolsa de mercadería",), reputacion_delta=6),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 6. Cibercafé
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="cibercafe",
    ubicacion="Cibercafé de la esquina, monitores CRT y olor a pucho",
    narracion=(
        "El módem hace ese ruido característico, como de robot mareado, antes "
        "de conectar. El cibercafé cobra por media hora y el dueño no te saca "
        "los ojos de encima. En la pantalla gruesa y curva, entre ventanas de "
        "MSN que tardan una eternidad en cargar, ves el noticiero de fondo en "
        "un televisor viejo: Crónica TV con la placa roja, \"CAOS EN TODO EL "
        "PAÍS\", mientras suena bajito una radio con cumbia villera desde el "
        "kiosco de al lado."
    ),
    imagen_en=(
        "the inside of a small internet cafe with rows of bulky CRT monitors, "
        "a few teenagers using computers, an old television in the corner "
        "showing a news broadcast with a red breaking-news graphic"
    ),
    opciones=(
        Opcion(texto="Revisar si hay algún mail o mensaje de gente conocida", destino="cibercafe_noticia"),
        Opcion(texto="Quedarte mirando las noticias en la tele para saber qué está pasando", destino="cibercafe_noticia",
               reputacion_delta=1),
        Opcion(
            texto="Revisar entre las cosas viejas del local por si encontrás lo que te pidió la del comedor",
            destino="cibercafe",
            requiere_flag="mision_comedor_activa",
            excluye_flag="encargo_encontrado",
            flags_add=("encargo_encontrado",),
            items_add=("encargo de Doña Rosa",),
            mensaje_efecto="Detrás de una torre de CPUs rotas, encontrás justo lo que te habían pedido.",
        ),
        Opcion(texto="Salir, esto no te sirve de mucho ahora", destino="volver_al_hub"),
    ),
    destino_libre="cibercafe_noticia",
))

_registrar(Nodo(
    id="cibercafe_noticia",
    ubicacion="Cibercafé de la esquina",
    narracion=(
        "Entre cortes de conexión y el módem cayéndose dos veces, conseguís "
        "algo de información: hablan de saqueos a un supermercado chino a diez "
        "cuadras, de asambleas en otros barrios, del estado de sitio decretado "
        "esta tarde. Si estabas buscando noticias de alguien en particular, esto "
        "es lo más cerca que vas a estar por ahora de un rastro."
    ),
    opciones=(
        Opcion(
            texto="Ir para el supermercado donde dicen que hay saqueo, por si tu gente anda ahí",
            destino="saqueo_supermercado",
            flags_add=("buscando_familiar",),
        ),
        Opcion(texto="Volver a tu barrio, es muy arriesgado ir para allá solo", destino="volver_al_hub"),
        Opcion(texto="Ir a la asamblea a pedir ayuda para buscar", destino="asamblea_barrial",
               reputacion_delta=2),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 7. Saqueo
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="saqueo_supermercado",
    ubicacion="Supermercado chino, sobre la avenida",
    narracion=(
        "Desde media cuadra ya se escucha el quilombo: vidrios rotos, alarmas "
        "que nadie apaga, gente saliendo con changuitos cargados hasta arriba. "
        "El dueño y su familia están atrincherados en la puerta con palos, "
        "gritando en una mezcla de mandarín y castellano que ya nadie escucha. "
        "Un patrullero está parado a media cuadra, sin animarse a entrar solo. "
        "El calor, el olor a mercadería derramada y a miedo lo llena todo."
    ),
    imagen_en=(
        "chaotic looting scene outside a small Chinese-owned supermarket in Buenos Aires, "
        "December 2001, desperate crowd carrying shopping carts full of goods, the owner's "
        "family barricading the entrance with sticks, a police car parked at a distance, "
        "gritty and tense atmosphere"
    ),
    opciones=(
        Opcion(
            texto="Sumarte a llevarte algo de comida, como todos",
            destino="saqueo_participar",
            requiere_camino="malo",
        ),
        Opcion(
            texto="Ayudar al dueño a defender la puerta en vez de robar",
            destino="saqueo_ayudar_dueno",
            requiere_camino="bueno",
        ),
        Opcion(
            texto="Buscar entre la gente si reconocés a la persona que estás buscando",
            destino="volver_al_hub",
            requiere_flag="buscando_familiar",
            destino_alt="volver_al_hub",
        ),
        Opcion(
            texto="Revolver entre los estantes tirados por si encontrás lo que te pidió la del comedor",
            destino="saqueo_supermercado",
            requiere_flag="mision_comedor_activa",
            excluye_flag="encargo_encontrado",
            flags_add=("encargo_encontrado",),
            items_add=("encargo de Doña Rosa",),
            salud_delta=(-5, 0),
            mensaje_efecto="Entre las góndolas volcadas, encontrás justo lo que te habían encargado.",
        ),
        Opcion(texto="Rajar de ahí, esto se puede poner muy feo", destino="volver_al_hub",
               salud_delta=(-3, 0)),
    ),
    destino_libre="saqueo_participar",
))

_registrar(Nodo(
    id="saqueo_participar",
    ubicacion="Adentro del supermercado saqueado",
    narracion=(
        "Entrás en el remolino. Te cruzás con vecinos conocidos cargando "
        "paquetes de fideos, con desconocidos empujándose por una garrafa. "
        "Alguien te grita que te apures, que la cana está por entrar. Agarrás "
        "lo que podés, sabiendo que en cualquier momento esto puede terminar a "
        "los tiros."
    ),
    opciones=(
        Opcion(
            texto="Agarrar lo justo y necesario, y salir cuanto antes",
            destino="volver_al_hub",
            destino_alt="persecucion",
            prob_alt=0.3,
            items_add=("bolsa de mercadería",),
            reputacion_delta=-3,
            alineacion_delta=-8,
        ),
        Opcion(
            texto="Quedarte cargando todo lo que puedas, total ya estás adentro",
            destino="volver_al_hub",
            destino_alt="persecucion",
            prob_alt=0.55,
            items_add=("bolsa de mercadería", "un televisor chico"),
            reputacion_delta=-10,
            alineacion_delta=-15,
            salud_delta=(-10, 0),
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="saqueo_ayudar_dueno",
    ubicacion="Puerta del supermercado",
    narracion=(
        "Te plantás al lado del dueño, que te mira sorprendido un segundo antes "
        "de pasarte un palo de escoba. Entre los dos y su familia arman una "
        "barrera humana en la puerta. No es fácil: hay empujones, algún golpe "
        "perdido, gritos de \"garca\" para el que se pone del lado del comerciante. "
        "Pero de a poco, la marea de gente empieza a desviarse hacia otro local "
        "más desprotegido."
    ),
    opciones=(
        Opcion(
            texto="Quedarte hasta que se calme del todo",
            destino="volver_al_hub",
            salud_delta=(-15, -4),
            reputacion_delta=10,
            alineacion_delta=12,
            flags_add=("defendiste_comercio",),
            items_add=("bolsa de mercadería",),
            mensaje_efecto="El dueño, agradecido, te arma una bolsa con algo de mercadería.",
        ),
        Opcion(
            texto="Irte apenas baja la tensión, ya hiciste lo que pudiste",
            destino="volver_al_hub",
            salud_delta=(-8, -2),
            reputacion_delta=6,
            alineacion_delta=6,
        ),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 8. Capítulo 2 — 19 de diciembre, la noche del cacerolazo
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="cacerolazo_19",
    ubicacion="Tu barrio, noche del 19 de diciembre",
    narracion=(
        "Cadena nacional. De la Rúa aparece en la tele con la cara gris y "
        "declara el estado de sitio. No termina de hablar cuando ya se "
        "escucha el primer golpe de cacerola en un balcón, después otro, "
        "después diez, después ya no se pueden contar. En minutos, medio "
        "país está en la calle o en la ventana, golpeando lo que tenga a "
        "mano. Nadie organizó esto. Pasó solo."
    ),
    imagen_en=(
        "a spontaneous nationwide cacerolazo protest at night in a Buenos Aires "
        "neighborhood, people banging pots and pans from balconies and windows, "
        "December 19 2001, dramatic wide shot, streetlights"
    ),
    dialogos=(
        ("Vecino del quinto piso", "¡Che, bajá con la cacerola, no te quedes mirando!"),
    ),
    opciones=(
        Opcion(
            texto="Bajar a la calle y sumarte al cacerolazo",
            destino="amanecer_20",
            reputacion_delta=4,
            alineacion_delta=5,
        ),
        Opcion(
            texto="Quedarte en tu casa mirando por la ventana, sin meterte",
            destino="amanecer_20",
        ),
        Opcion(
            texto="Aprovechar que la policía está desbordada para forzar la persiana de un local cerrado",
            destino="amanecer_20",
            destino_alt="persecucion",
            prob_alt=RIESGO_MEDIO,
            items_add=("bolsa de mercadería",),
            alineacion_delta=-15,
            reputacion_delta=-8,
        ),
    ),
    destino_libre="amanecer_20",
    capitulo=2,
))


# ---------------------------------------------------------------------------
# 9. Capítulo 3 — 20 de diciembre, el día del estallido
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="amanecer_20",
    ubicacion="Tu barrio, mañana del 20 de diciembre",
    narracion=(
        "Amanece distinto. La radio dice que anoche saquearon supermercados "
        "en todo el país, que ya hay muertos en Rosario, que en Plaza de "
        "Mayo se está juntando gente desde temprano. Hoy va a ser el peor "
        "día. Tenés que decidir dónde parate."
    ),
    imagen_en=(
        "a residential Buenos Aires street early in the morning after a night of "
        "looting, a small group of neighbors gathered around a portable radio "
        "listening to the news, distant smoke rising over the city skyline"
    ),
    dialogos=(
        ("Locutor de radio", "Se pide a la población que evite circular por el microcentro..."),
    ),
    opciones=(
        Opcion(texto="Ir para el supermercado del barrio, donde dicen que hay saqueo", destino="saqueo_supermercado"),
        Opcion(texto="Ir para Plaza de Mayo, donde se está juntando la gente", destino="plaza_de_mayo"),
        Opcion(texto="Quedarte ayudando en el comedor del barrio", destino="comedor"),
        Opcion(texto="Quedarte en tu casa, esperar que pase el día", destino="noticia_renuncia"),
    ),
    destino_libre="amanecer_20",
    destino_cansancio="noticia_renuncia",
    capitulo=3,
))

_registrar(Nodo(
    id="plaza_de_mayo",
    ubicacion="Plaza de Mayo, mediodía del 20 de diciembre",
    narracion=(
        "Nunca viste tanta gente junta. Se mezcla todo: familias con "
        "banderas argentinas, militantes de organizaciones piqueteras, "
        "oficinistas que salieron a la hora del almuerzo y ya no se fueron, "
        "gente golpeando cacerolas al ritmo de \"que se vayan todos\". El "
        "cordón de la policía montada rodea la Casa Rosada, tenso, esperando "
        "una orden."
    ),
    imagen_en=(
        "a massive crowd gathering at Plaza de Mayo in Buenos Aires, December 20 2001, "
        "national flags, banging pots, mounted police forming a line near the pink "
        "presidential palace in the background, tense atmosphere, midday"
    ),
    opciones=(
        Opcion(
            texto="Sumarte a los cánticos en la primera línea, frente a la policía",
            destino="represion",
            reputacion_delta=3,
        ),
        Opcion(
            texto="Sumarte a un grupo que empieza a quemar gomas y armar una barricada",
            destino="piquetero_violento_1",
            alineacion_delta=-15,
            requiere_camino="malo",
        ),
        Opcion(
            texto="Quedarte en el fondo de la plaza, mirando de lejos",
            destino="represion",
            destino_alt="noticia_renuncia",
            prob_alt=0.4,
        ),
    ),
    destino_libre="represion",
    capitulo=3,
))

_registrar(Nodo(
    id="piquetero_violento_1",
    ubicacion="Un costado de Plaza de Mayo, entre el humo",
    narracion=(
        "Las gomas arden y el humo negro se mezcla con los primeros gases. "
        "Alguien grita que la montada va a cargar. Tenés en la mano lo que "
        "juntaste para la barricada: piedras, un palo, una botella con nafta "
        "que te pasó un pibe sin decir una palabra."
    ),
    imagen_en=(
        "burning tires and a makeshift barricade at the edge of Plaza de Mayo, Buenos "
        "Aires December 20 2001, thick black smoke, protesters throwing stones, mounted "
        "police charging in the background, dramatic action shot"
    ),
    opciones=(
        Opcion(
            texto="Tirar piedras y aguantar la línea con los demás",
            destino="piquetero_violento_2",
            destino_alt="persecucion",
            prob_alt=0.3,
            alineacion_delta=-10,
            salud_delta=(-10, -2),
        ),
        Opcion(
            texto="Prender la botella y tirarla contra un carro policial",
            destino="piquetero_violento_2",
            destino_alt="persecucion",
            prob_alt=0.4,
            alineacion_delta=-20,
            flags_add=("tiraste_molotov",),
            salud_delta=(-15, -5),
        ),
        Opcion(
            texto="Rajar de ahí ahora que todavía podés",
            destino="represion",
        ),
        Opcion(
            texto="Aceptar la pastilla que te ofrece un pibe \"para aguantar\"",
            destino="efecto_sustancia_piquete",
        ),
    ),
    destino_libre="piquetero_violento_2",
    capitulo=3,
))

_registrar(Nodo(
    id="piquetero_violento_2",
    ubicacion="Plaza de Mayo, la represión se pone brava",
    narracion=(
        "La carga se puso seria: caballos, gases, alguien cerca tuyo se cae "
        "y no se levanta. Un policía te agarra de la campera. Tenés una "
        "fracción de segundo para decidir qué hacer."
    ),
    imagen_en=(
        "mounted police charging through tear gas at Plaza de Mayo, Buenos Aires "
        "December 20 2001, chaotic and violent scene, protesters running and "
        "fighting back, dramatic low angle"
    ),
    opciones=(
        Opcion(
            texto="Pegarle para zafar de su mano y perderte en el humo",
            destino="noticia_renuncia",
            destino_alt="persecucion",
            prob_alt=0.45,
            alineacion_delta=-15,
            flags_add=("zafaste_de_la_cana",),
            salud_delta=(-15, -5),
        ),
        Opcion(
            texto="Ayudar a sacar de ahí a un compañero herido, aunque te agarren",
            destino="noticia_renuncia",
            destino_alt="persecucion",
            prob_alt=0.35,
            reputacion_delta=8,
            alineacion_delta=-5,
            flags_add=("salvaste_a_alguien",),
            salud_delta=(-20, -8),
        ),
        Opcion(
            texto="Resistir hasta el final, cueste lo que cueste",
            destino="noticia_renuncia",
            destino_alt="persecucion",
            prob_alt=0.5,
            alineacion_delta=-20,
            flags_add=("resististe_hasta_el_final",),
            salud_delta=(-30, -10),
        ),
    ),
    destino_libre="persecucion",
    capitulo=3,
))

_registrar(Nodo(
    id="noticia_renuncia",
    ubicacion="Gran Buenos Aires, media tarde del 20 de diciembre",
    narracion=(
        "Corre como reguero de pólvora, de radio en radio, de balcón en "
        "balcón: De la Rúa renunció. Poco después, la imagen que va a "
        "quedar grabada para siempre: un helicóptero despegando desde la "
        "terraza de la Casa Rosada, mientras abajo la plaza sigue ardiendo. "
        "El estado de sitio sigue vigente, pero ya nada de esto se puede "
        "parar con un decreto."
    ),
    imagen_en=(
        "a helicopter taking off from the rooftop of the pink presidential palace at dusk, "
        "seen from a chaotic crowded plaza below still filled with smoke, Buenos Aires "
        "December 20 2001, historic and dramatic moment"
    ),
    opciones=(
        Opcion(texto="Volver para tu barrio a ver cómo sigue todo", destino="semana_presidentes_1"),
        Opcion(texto="Quedarte un rato más viendo cómo termina el día en la calle", destino="semana_presidentes_1",
               reputacion_delta=2),
    ),
    destino_libre="semana_presidentes_1",
    capitulo=3,
))


# ---------------------------------------------------------------------------
# 10. Capítulos 4-6 — La semana de los presidentes
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="semana_presidentes_1",
    ubicacion="Tu barrio, los días de Puerta interino",
    narracion=(
        "Ramón Puerta asume interino mientras el Congreso decide qué hacer. "
        "Nadie sabe bien qué va a pasar mañana, y mucho menos la semana que "
        "viene. La vida sigue, como puede: hay que comer, hay que curarse "
        "las heridas de estos días, hay que ver qué hacer con lo poco que "
        "queda."
    ),
    imagen_en=(
        "a neighborhood corner in a Buenos Aires suburb, a small group of "
        "neighbors talking near a corner store with a handwritten sign about "
        "accepting Patacones, ordinary daytime activity resuming cautiously "
        "after days of chaos"
    ),
    opciones=(
        Opcion(texto="Ir al club de trueque a ver qué conseguís", destino="club_trueque"),
        Opcion(texto="Ir a la asamblea del barrio", destino="asamblea_barrial", requiere_camino="bueno"),
        Opcion(texto="Pasar por el comedor", destino="comedor"),
        Opcion(texto="Ir al hospital si lo necesitás", destino="hospital", requiere_salud_maxima=80),
        Opcion(texto="Pasar por el cibercafé", destino="cibercafe"),
        Opcion(texto="Parar en el bar de la esquina a ver si se te pasa el nudo en el estómago", destino="bar_de_la_esquina"),
        Opcion(texto="Intentar irte del Conurbano/CABA", destino="control_ruta"),
    ),
    destino_libre="semana_presidentes_1",
    destino_cansancio="semana_presidentes_2",
    capitulo=4,
))

_registrar(Nodo(
    id="tren_cartoneros",
    ubicacion="Andén de la estación, de noche",
    narracion=(
        "El tren llega tarde y va casi vacío de asientos, pero lleno de "
        "carros y bolsones de cartón y papel amontonados entre los vagones. "
        "Sube gente de todas las edades, familias enteras, algunos con "
        "chicos dormidos arriba de la mercadería. Es la nueva rutina de "
        "medio conurbano: juntar en la Capital lo que en el barrio ya no "
        "hay, y volver de madrugada."
    ),
    imagen_en=(
        "a busy train platform at night with a crowd of Argentine people waiting "
        "for the informal cartoneros train, a train with visible open cargo wagons "
        "stopped at the platform, some people pushing small carts loaded with "
        "bundles of cardboard, dim yellow station lighting, medium wide shot"
    ),
    dialogos=(
        ("Señora del carro", "Antes yo era administrativa, ¿sabés? Ahora junto cartón. Así estamos."),
    ),
    opciones=(
        Opcion(
            texto="Subirte a juntar cartón vos también, para hacer una moneda",
            destino="volver_al_hub",
            dinero_delta={"creditos_trueque": 8},
            alineacion_delta=2,
            flags_add=("trabajaste_de_cartonero",),
            salud_delta=(-8, -2),
        ),
        Opcion(
            texto="Ayudar a subir los bolsones de una señora mayor sin cobrar nada",
            destino="volver_al_hub",
            reputacion_delta=8,
            alineacion_delta=10,
        ),
        Opcion(texto="Mirar desde el andén y no subir, seguir tu camino", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="semana_presidentes_2",
    ubicacion="Tu barrio, la semana de Rodríguez Saá",
    narracion=(
        "Asume Adolfo Rodríguez Saá, elegido por la Asamblea Legislativa. En "
        "su discurso anuncia la suspensión del pago de la deuda externa; los "
        "diputados lo aplauden de pie. En la calle, la euforia dura poco: la "
        "plata que no había ayer tampoco apareció hoy. A la noche, el tren "
        "de los cartoneros pasa cada vez más lleno."
    ),
    imagen_en=(
        "a neighborhood street in Buenos Aires at dusk, neighbors going about "
        "daily errands, a small crowd gathered around a portable television in "
        "a storefront window watching a presidential address"
    ),
    opciones=(
        Opcion(texto="Ir a la estación a ver pasar (o subirte a) el tren de los cartoneros", destino="tren_cartoneros"),
        Opcion(texto="Ir al club de trueque", destino="club_trueque"),
        Opcion(texto="Pasar por el comedor", destino="comedor"),
        Opcion(texto="Ir al hospital si lo necesitás", destino="hospital", requiere_salud_maxima=80),
        Opcion(texto="Ir a la asamblea del barrio", destino="asamblea_barrial", requiere_camino="bueno"),
        Opcion(texto="Parar en el bar de la esquina un rato", destino="bar_de_la_esquina"),
    ),
    destino_libre="semana_presidentes_2",
    destino_cansancio="semana_presidentes_3",
    capitulo=5,
))

_registrar(Nodo(
    id="semana_presidentes_3",
    ubicacion="Tu barrio, fin de año",
    narracion=(
        "Rodríguez Saá renuncia a los pocos días, después de piquetes y "
        "saqueos que no dieron tregua. El 1° de enero asume Eduardo Duhalde, "
        "elegido otra vez por la Asamblea Legislativa: el quinto presidente "
        "en dos semanas. La convertibilidad, el uno a uno que sostuvo diez "
        "años de vida cotidiana, tiene los días contados. Lo agudo de la "
        "crisis empieza, por fin, a asentarse en algo parecido a una nueva "
        "normalidad, aunque sea una normalidad rota."
    ),
    imagen_en=(
        "a Buenos Aires neighborhood street on New Year's Eve, modest fireworks "
        "in the distance, groups of neighbors sitting outside their houses on "
        "the sidewalk on a warm summer night, a subdued atmosphere"
    ),
    opciones=(
        Opcion(texto="Ir al club de trueque", destino="club_trueque"),
        Opcion(texto="Pasar por el comedor", destino="comedor"),
        Opcion(texto="Ir al hospital si lo necesitás", destino="hospital", requiere_salud_maxima=80),
        Opcion(texto="Parar en el bar de la esquina antes de volver", destino="bar_de_la_esquina"),
        Opcion(texto="Volver a tu barrio a parar la pelota", destino="calle_noche"),
    ),
    destino_libre="calle_noche",
    destino_cansancio="calle_noche",
    capitulo=6,
))


# ---------------------------------------------------------------------------
# 11. Capítulo 7 — Cierre
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="calle_noche",
    ubicacion="Tu barrio, ya pasada la peor semana",
    narracion=(
        "Cae la noche sobre un Gran Buenos Aires que no se parece en nada al "
        "de hace dos semanas. A lo lejos siguen las cacerolas, más cansadas "
        "ahora, casi un arrullo triste. Tenés que decidir qué hacer con lo "
        "que te queda de fuerzas."
    ),
    imagen_en=(
        "a quiet Buenos Aires neighborhood street late at night after weeks of "
        "crisis, a few neighbors still sitting out on the sidewalk, a tired and "
        "calmer mood than the chaos of prior weeks"
    ),
    salud_entrada=(-2, 1),
    opciones=(
        Opcion(texto="Volver a tu casa a descansar y esperar que amanezca", destino="final_decision",
               salud_delta=(3, 8)),
        Opcion(texto="Intentar irte del Conurbano/CABA de una vez por todas", destino="control_ruta"),
        Opcion(texto="Quedarte en la calle, con los vecinos, pase lo que pase", destino="final_decision",
               reputacion_delta=6, alineacion_delta=6),
        Opcion(
            texto="Acercarte a la Casa Rosada, que en medio de este quilombo quedó rarísimamente desprotegida",
            destino="casa_rosada_exterior",
        ),
    ),
    destino_libre="final_decision",
    capitulo=7,
))


# ---------------------------------------------------------------------------
# 9. Finales
# ---------------------------------------------------------------------------
# "final_decision" es un nodo técnico: el motor lo intercepta y redirige de
# inmediato al final correspondiente según el estado acumulado (ver
# engine.elegir_final). No debería quedar nunca mostrado en pantalla.

_registrar(Nodo(
    id="final_decision",
    ubicacion="",
    narracion="",
    opciones=(),
))

_registrar(Nodo(
    id="final_muerte",
    ubicacion="Gran Buenos Aires, diciembre de 2001",
    narracion=(
        "Todo se apaga de golpe, como un televisor de tubo al que le cortan la "
        "luz. No hay heroísmo en esto, no hay música de fondo: sos uno más de "
        "los nombres que se van a leer al otro día en Crónica, entre las placas "
        "rojas. El caos sigue, indiferente, afuera."
    ),
    imagen_en=(
        "somber and quiet aftermath scene on a Buenos Aires street at night, December 2001, "
        "a single dim streetlight, distant smoke still rising, an empty pair of shoes on the "
        "pavement, melancholic and grim atmosphere"
    ),
    es_final=True,
    final_tipo="muerte",
))

_registrar(Nodo(
    id="final_muerte_manifestacion",
    ubicacion="Gran Buenos Aires, diciembre de 2001",
    narracion=(
        "No sentís el golpe, solo el suelo. Alguien grita que llamen a una "
        "ambulancia, pero entre el gas, la gente corriendo y las calles "
        "cortadas, tarda demasiado en llegar. Te suben como pueden. En el "
        "país que se está por quedar sin cinco presidentes en dos semanas, "
        "un nombre más en la lista de esa tarde no le cambia el rumbo a "
        "nadie. Menos a vos."
    ),
    imagen_en=(
        "a somber scene of an ambulance arriving too late at a chaotic protest scene at "
        "night, Buenos Aires December 2001, paramedics and bystanders around a fallen "
        "person, tear gas haze, grim and quiet aftermath"
    ),
    es_final=True,
    final_tipo="muerte_manifestacion",
))

_registrar(Nodo(
    id="final_cartonero",
    ubicacion="Andén de la estación, muchas noches después",
    narracion=(
        "Terminaste subiéndote al tren de los cartoneros todas las noches, "
        "no una vez de casualidad sino como rutina. No es lo que soñabas, "
        "ni por asomo, pero el carro se paga solo, y las bolsas de cartón "
        "de esta semana valen más que la libreta del banco que ya nadie "
        "mira. Sobreviviste, a tu manera: rejuntando lo que el país tira, "
        "para no ser vos el que quede tirado."
    ),
    imagen_en=(
        "a person pulling a cardboard-collecting cart (cartonero) along a dark Buenos "
        "Aires street at dawn, December 2001, exhausted but resolute expression, city "
        "lights in the background, documentary photojournalism framing"
    ),
    es_final=True,
    final_tipo="cartonero",
))

_registrar(Nodo(
    id="final_referente_piquetero",
    ubicacion="Corte de ruta, meses después",
    narracion=(
        "Nunca decidiste convertirte en nada. Pasó solo, a fuerza de estar "
        "en cada corte, en cada barricada, de no bajar los brazos ni "
        "cuando la cana cargaba en serio. Ahora, cuando llegás a un piquete, "
        "la gente te abre lugar en la primera línea sin preguntar. Hiciste "
        "todo lo que en cualquier otro país te habría mandado preso para "
        "siempre —quemaste gomas, tiraste una molotov, te trenzaste a "
        "golpes con la policía— y sin embargo estás acá, parado, respetado, "
        "libre. En el Gran Buenos Aires de esta crisis, a veces el camino "
        "de afuera de la ley es el único que te deja de pie al final."
    ),
    imagen_en=(
        "a respected grassroots protest leader (piquetero referente) standing confidently "
        "at the front of a highway roadblock, surrounded by supporters, burnt tires in the "
        "background, Buenos Aires conurbano months after the crisis, determined and heroic "
        "framing despite the gritty setting"
    ),
    es_final=True,
    final_tipo="referente_piquetero",
))

_registrar(Nodo(
    id="final_objetivo_cumplido",
    ubicacion="Gran Buenos Aires, diciembre de 2001",
    narracion=(
        "Contra todos los pronósticos, conseguiste lo que habías salido a "
        "buscar. No fue limpio ni fue fácil, y seguramente vas a llevar marcas "
        "de este día por mucho tiempo, pero lo lograste. Mientras a tu "
        "alrededor el país se sigue cayendo a pedazos, vos por lo menos podés "
        "decir que este objetivo puntual no te lo llevó puesto."
    ),
    imagen_en=(
        "a quiet moment of personal relief amid urban chaos in Buenos Aires, December 2001, "
        "a person holding something precious close, distant fires and protest smoke in the "
        "background, bittersweet cinematic lighting"
    ),
    es_final=True,
    final_tipo="objetivo_cumplido",
))

_registrar(Nodo(
    id="final_comunidad",
    ubicacion="Placita del barrio, madrugada",
    narracion=(
        "No lo resolviste solo, y quizás por eso lo resolviste. Entre asambleas, "
        "trueques y una mano tendida en el momento justo, terminaste construyendo "
        "algo que ni el Corralito ni los Patacones ni la cana pudieron romper: "
        "una red de gente que se banca entre sí. \"Que se vayan todos\" siguió "
        "sonando toda la noche, pero al menos vos no estás solo escuchándolo."
    ),
    imagen_en=(
        "a warm nighttime scene of neighbors gathered around a communal pot (olla popular) "
        "in a Buenos Aires neighborhood square, December 2001, makeshift lanterns, a sense "
        "of solidarity amid the crisis"
    ),
    es_final=True,
    final_tipo="comunidad",
))

_registrar(Nodo(
    id="final_perdido",
    ubicacion="Un lugar que ya no reconocés bien",
    narracion=(
        "En algún momento de estas semanas dejaste de volver. Lo que empezó "
        "como una forma de aguantar la angustia —una petaca, un porro, una "
        "pastilla para no sentir tanto— se convirtió en el único lugar donde "
        "las cosas no dolían tanto. El objetivo que te trajo hasta acá, la "
        "familia, el negocio, la plata del banco, se te fue desdibujando "
        "hasta quedar lejísimos. El país sigue su curso allá afuera, con o "
        "sin vos prestando atención."
    ),
    imagen_en=(
        "a person sitting alone in a dim room surrounded by empty bottles, lost in a haze, "
        "Buenos Aires December 2001, muted and melancholic lighting, respectful and "
        "non-graphic depiction of addiction and despair"
    ),
    es_final=True,
    final_tipo="perdido",
))

_registrar(Nodo(
    id="final_solitario",
    ubicacion="Tu casa, de madrugada",
    narracion=(
        "Sobreviviste. Eso, al menos, te lo podés quedar. Pero lo hiciste solo, "
        "a los ponchazos, sin sumarte del todo a nada ni a nadie. Desde la cama "
        "escuchás las cacerolas cada vez más lejos, como si el barrio siguiera "
        "girando sin vos. Mañana va a ser otro día largo en un país que todavía "
        "no toca fondo."
    ),
    imagen_en=(
        "a person lying awake alone in a dim room lit by a small CRT television playing "
        "news static, Buenos Aires December 2001, distant window view of the city at night, "
        "quiet and isolated mood"
    ),
    es_final=True,
    final_tipo="solitario",
))


# ---------------------------------------------------------------------------
# 10. Piquete (corte de ruta)
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="piquete",
    ubicacion="Corte de ruta en el acceso al barrio",
    narracion=(
        "Un piquete cortó la ruta de acceso: gomas quemadas, bidones vacíos, "
        "una hilera de banderas de distintas organizaciones flameando juntas "
        "por primera vez en mucho tiempo. Los autos varados hacen sonar la "
        "bocina, algunos putean por la ventanilla, otros bajan a preguntar qué "
        "está pasando y se quedan. El humo negro de las gomas te raspa la "
        "garganta antes de que llegues."
    ),
    imagen_en=(
        "a highway roadblock (piquete) with burning tires, a row of protest "
        "flags from different organizations, a crowd of picketers standing "
        "their ground while stopped cars line up in the background, thick "
        "black smoke"
    ),
    dialogos=(
        ("Referente del piquete", "Acá no cortamos por joder, hermano. Cortamos porque no nos dejan otra."),
    ),
    opciones=(
        Opcion(texto="Sumarte al corte activamente, hombro con hombro", destino="piquete_resistencia",
               reputacion_delta=6),
        Opcion(texto="Quedarte en la periferia, mirando cómo sigue esto", destino="piquete_resistencia"),
        Opcion(texto="Intentar mediar con los automovilistas para bajar la tensión", destino="piquete_resistencia",
               reputacion_delta=3),
    ),
    destino_libre="piquete_resistencia",
))


# ---------------------------------------------------------------------------
# 8bis. Cortar una ruta en un barrio ajeno — sidequest de tiempo perdido
# ---------------------------------------------------------------------------
# A diferencia del piquete de tu propio barrio (arriba), acá no conocés a
# nadie ni tenés ningún arraigo: es un movimiento más al voleo, más "camino
# malo" por elección pura. El riesgo no es principalmente la salud o la
# cárcel (aunque también puede pasar), sino el TIEMPO: con 70% de
# probabilidad la vuelta se complica y perdés un día entero, saltando de
# golpe al día del estallido (capítulo 3) sin pasar por el resto del
# capítulo 1 ni por el cacerolazo del capítulo 2 — lo que puede dejarte sin
# margen para conseguir objetivos que solo estaban disponibles antes (por
# ejemplo, el trámite del banco).

_registrar(Nodo(
    id="piquete_ruta_ajena",
    ubicacion="Ruta de acceso a otro barrio, lejos de tu zona",
    narracion=(
        "Te subiste a un colectivo y cruzaste medio conurbano para sumarte a "
        "un corte del que te enteraste por un conocido de un conocido. Acá no "
        "te conoce nadie: ni los referentes, ni los vecinos, ni la policía que "
        "eventualmente va a venir. Es otra cosa, más cruda, sin la contención "
        "de tu propio barrio."
    ),
    imagen_en=(
        "a highway roadblock far from home at dusk, an unfamiliar crowd of "
        "picketers from a neighborhood the viewer does not recognize, burning "
        "tires, tense atmosphere, a person standing awkwardly at the edge of "
        "the crowd not quite belonging"
    ),
    opciones=(
        Opcion(
            texto="Quedarte hasta el final, pase lo que pase",
            destino="volver_al_hub",
            destino_alt="piquete_ruta_ajena_mal",
            prob_alt=0.7,
            alineacion_delta=-10,
            salud_delta=(-10, -3),
            flags_add=("corte_ruta_ajena",),
            mensaje_efecto="Aguantás el corte hasta que se disuelve solo, de puro cansancio colectivo.",
        ),
        Opcion(
            texto="Arrepentirte a mitad de camino y volver antes de que oscurezca",
            destino="volver_al_hub",
            alineacion_delta=-3,
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="piquete_ruta_ajena_mal",
    ubicacion="Muy lejos de tu casa, bastante después de lo planeado",
    narracion=(
        "Se complicó todo: primero un amague de represión que te hizo correr "
        "en la dirección equivocada, después no había forma de volver con los "
        "cortes y los colectivos parados en toda la zona. Terminás durmiendo "
        "en la casa de alguien que conociste esa misma tarde, y quemás un día "
        "entero de tu vida en esto que ni siquiera era tu pelea. Volvés al día "
        "siguiente, tarde, con la sensación de haber perdido un tiempo que no "
        "te sobraba."
    ),
    imagen_en=(
        "a person walking alone at dawn along an unfamiliar highway shoulder, "
        "exhausted, far from home, the previous night's chaos left behind"
    ),
    opciones=(
        Opcion(
            texto="Volver como puedas a tu barrio y seguir adelante",
            destino="amanecer_20",
            salud_delta=(-15, -5),
            reputacion_delta=-3,
            alineacion_delta=-8,
            flags_add=("perdiste_un_dia",),
        ),
    ),
    destino_libre="amanecer_20",
))

_registrar(Nodo(
    id="piquete_resistencia",
    ubicacion="Corte de ruta",
    narracion=(
        "Pasan las horas y el corte se sostiene. Alguien trae mate y pan, otro "
        "cuenta chistes malos para bajar la tensión. Pero a lo lejos, entre el "
        "humo de las gomas, empiezan a distinguirse las luces azules y rojas "
        "de una hilera de patrulleros que se acerca despacio, sin apuro, como "
        "quien sabe que tiene todo el tiempo del mundo."
    ),
    opciones=(
        Opcion(texto="Prepararte para resistir el corte pase lo que pase", destino="piquete_represion",
               reputacion_delta=4),
        Opcion(texto="Empezar a pensar por dónde vas a rajar si esto se pone feo", destino="piquete_represion"),
        Opcion(texto="Proponer levantar el corte antes de que llegue la cana", destino="volver_al_hub",
               reputacion_delta=-2),
    ),
    destino_libre="piquete_represion",
))

_registrar(Nodo(
    id="piquete_represion",
    ubicacion="Corte de ruta, bajo represión",
    narracion=(
        "No negocian: la gendarmería avanza en línea, escudos y gases, y detrás "
        "un camión hidrante que ya empieza a barrer la primera fila del corte. "
        "En segundos el piquete ordenado se convierte en una desbandada de "
        "gente corriendo entre el humo, tropezando con las gomas que un minuto "
        "antes eran la barricada."
    ),
    imagen_en=(
        "riot police in full gear advancing on a burning highway roadblock (piquete) with "
        "tear gas and a water cannon truck, protesters scattering in panic, Buenos Aires "
        "December 2001, dramatic wide action shot"
    ),
    opciones=(
        Opcion(
            texto="Resistir en la primera línea, no vas a aflojar",
            destino="volver_al_hub",
            destino_alt="final_represion_piquete",
            prob_alt=0.65,
            salud_delta=(-20, -8),
            estados_add=("tos por gases",),
            reputacion_minima_favorable=15,
            bonus_reputacion_favorable=0.1,
            bonus_salud_reputacion=8,
        ),
        Opcion(
            texto="Retirarte rápido hacia atrás, entre la desbandada",
            destino="volver_al_hub",
            destino_alt="final_represion_piquete",
            prob_alt=0.35,
            salud_delta=(-10, -2),
            reputacion_minima_favorable=15,
            bonus_reputacion_favorable=0.1,
            bonus_salud_reputacion=6,
        ),
        Opcion(
            texto="Quedarte a un costado filmando la represión con lo que tengas a mano",
            destino="volver_al_hub",
            destino_alt="final_represion_piquete",
            prob_alt=0.5,
            salud_delta=(-15, -5),
            reputacion_delta=5,
            reputacion_minima_favorable=15,
            bonus_reputacion_favorable=0.1,
            bonus_salud_reputacion=8,
        ),
    ),
    destino_libre="final_represion_piquete",
))


# ---------------------------------------------------------------------------
# 11. Control de ruta — el límite del AMBA
# ---------------------------------------------------------------------------
# No hay forma de "ganar" saliendo del Conurbano/CABA: cualquier intento
# termina acá, y de acá siempre se vuelve para adentro. La única variable es
# cuánto te cuesta el intento (y si te pasás de vivo, terminás preso).

_registrar(Nodo(
    id="control_ruta",
    ubicacion="Peaje/control de acceso, límite del AMBA",
    narracion=(
        "Llegás al control y la fila de autos no se mueve: es un retén de "
        "gendarmería revisando documentos y baúles, uno por uno, mezclado con "
        "un corte de otro piquete del otro lado. Nadie entra ni sale del "
        "Conurbano sin pase esta noche. \"Con la que está armada, quedate en "
        "tu casa\", te dice un gendarme, sin mirarte demasiado."
    ),
    imagen_en=(
        "a long line of cars stopped at a highway toll checkpoint at night, "
        "gendarmerie officers checking documents and trunks one by one, road "
        "flares and roadblock signs, tense atmosphere"
    ),
    opciones=(
        Opcion(
            texto="Dar la vuelta, resignado, y volver a tu barrio",
            destino="volver_al_hub",
            salud_delta=(-3, 0),
            mensaje_efecto=(
                "No hay forma de cruzar esta noche: perdés el viaje entero de vuelta, "
                "cansado, y el día sigue corriendo igual mientras tanto."
            ),
        ),
        Opcion(
            texto="Intentar colarte campo traviesa, lejos del control",
            destino="volver_al_hub",
            destino_alt="carcel",
            prob_alt=0.25,
            salud_delta=(-8, -2),
            alineacion_delta=-8,
            item_desfavorable="un televisor chico",
            penalizacion_item_desfavorable=0.25,
        ),
        Opcion(
            texto="Discutir con el gendarme a cargo, exigir que te dejen pasar",
            destino="volver_al_hub",
            destino_alt="carcel",
            prob_alt=0.15,
            reputacion_delta=-3,
            alineacion_delta=-3,
            item_favorable="documento de identidad",
            bonus_item_favorable=0.1,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.2,
        ),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 12. Persecución policial
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="persecucion",
    ubicacion="Corriendo por las calles del barrio",
    narracion=(
        "\"¡Alto ahí!\" — un policía te vio y salió corriendo detrás tuyo, "
        "haciendo sonar un silbato. El corazón se te va a la garganta. Las "
        "calles se llenan de gente que se corre de en medio, algunos te miran, "
        "nadie te ayuda, nadie te delata tampoco."
    ),
    imagen_en=(
        "a person running desperately through a narrow Buenos Aires street being chased by "
        "a police officer on foot, December 2001, motion blur, dramatic low angle, tense "
        "nighttime chase scene"
    ),
    opciones=(
        Opcion(
            texto="Meterte en un zaguán abierto a esconderte",
            destino="volver_al_hub",
            destino_alt="persecucion_acorralado",
            prob_alt=0.35,
        ),
        Opcion(
            texto="Cruzar corriendo la avenida esquivando autos",
            destino="volver_al_hub",
            destino_alt="persecucion_acorralado",
            prob_alt=0.45,
            salud_delta=(-15, -5),
        ),
        Opcion(
            texto="Perderte entre la gente en la parada del colectivo",
            destino="volver_al_hub",
            destino_alt="persecucion_acorralado",
            prob_alt=0.3,
        ),
    ),
    destino_libre="persecucion_acorralado",
))

_registrar(Nodo(
    id="persecucion_acorralado",
    ubicacion="Callejón sin salida",
    narracion=(
        "Doblás en lo que pensabas que era una salida y no hay nada: pared "
        "ciega, rejas, un tacho de basura volcado. Atrás tuyo, dos policías "
        "entran al callejón caminando despacio, ya sin apuro. \"Quedate "
        "tranquilo y no va a pasar nada\", dice uno, con la mano en la cintura."
    ),
    opciones=(
        Opcion(texto="Levantar las manos y entregarte", destino="carcel"),
        Opcion(
            texto="Intentar zafar a las piñas",
            destino="volver_al_hub",
            destino_alt="carcel",
            prob_alt=0.75,
            salud_delta=(-30, -10),
            item_desfavorable="un televisor chico",
            penalizacion_item_desfavorable=0.15,
        ),
        Opcion(
            texto="Ofrecerles unos pesos para que te dejen ir",
            destino="volver_al_hub",
            destino_alt="carcel",
            prob_alt=0.4,
            dinero_delta={"pesos": -30},
        ),
    ),
    destino_libre="carcel",
))


# ---------------------------------------------------------------------------
# 13. Casa Rosada — el camino menos pensado
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="casa_rosada_exterior",
    ubicacion="Plaza de Mayo, frente a la Casa Rosada",
    narracion=(
        "Es una imagen que no vas a olvidar nunca: la Casa de Gobierno, "
        "prácticamente sola. El helicóptero presidencial se fue hace un rato "
        "largo, ya sin nadie mirando el cielo. No hay Granaderos en la puerta, "
        "no hay vallado, no hay nadie cuidando nada. En medio de semejante "
        "quilombo, a esta hora, nadie está mirando la Casa Rosada."
    ),
    imagen_en=(
        "the pink presidential palace (Casa Rosada) in Buenos Aires standing eerily "
        "unguarded at night during a state of chaos in December 2001, its side gates left "
        "open, distant sirens and glow of fires in the sky, empty plaza in the foreground"
    ),
    opciones=(
        Opcion(
            texto="Meterte por los jardines laterales",
            destino="casa_rosada_infiltracion",
            destino_alt="carcel",
            prob_alt=0.4,
        ),
        Opcion(
            texto="Treparte por una reja donde ya se ve gente entrando",
            destino="casa_rosada_infiltracion",
            destino_alt="carcel",
            prob_alt=0.3,
        ),
        Opcion(texto="Retirarte, esto es una locura", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="casa_rosada_infiltracion",
    ubicacion="Adentro de la Casa Rosada",
    narracion=(
        "Los pasillos están vacíos y en penumbras. Cuadros de próceres torcidos "
        "en la pared, papeles tirados por todos lados de la salida apurada de "
        "esta tarde. Caminás como en un sueño, sin que nadie te pare, hasta un "
        "salón enorme con un sillón al fondo, bajo un cuadro gigante. Nadie "
        "más parece estar ahí."
    ),
    imagen_en=(
        "the empty grand hall inside the Casa Rosada presidential palace at night, "
        "abandoned in haste, papers scattered on marble floors, a presidential chair "
        "illuminated at the far end, eerie and surreal atmosphere"
    ),
    opciones=(
        Opcion(texto="Sentarte en el sillón, total ¿quién te va a decir algo?", destino="final_presidente"),
        Opcion(
            texto="Agarrar algún recuerdo y rajar antes de que te agarren",
            destino="volver_al_hub",
            destino_alt="carcel",
            prob_alt=0.3,
            items_add=("un cuadro chico afanado de la Casa Rosada",),
        ),
        Opcion(texto="Arrepentirte y salir corriendo antes de que sea peor", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 14. Comisaría / cárcel — ya no es un final automático
# ---------------------------------------------------------------------------
# Caer preso no termina la partida de una: hay margen para mover algunas
# fichas (abogado, coima, aguantar la audiencia) antes de que se defina de
# verdad. El único final real de esta rama es final_condenado.

_registrar(Nodo(
    id="carcel",
    ubicacion="Comisaría del barrio",
    narracion=(
        "Te subieron al patrullero sin muchas explicaciones. La comisaría está "
        "desbordada, hay más gente detenida esta noche que espacio en los "
        "calabozos. Te sientan en un banco de madera con un número de "
        "expediente y te dicen que esperes. Todavía hay margen para mover "
        "algunas fichas antes de que esto se termine de definir."
    ),
    imagen_en=(
        "the overcrowded inside of a small local police station at night in Buenos Aires, "
        "December 2001, detained people sitting on benches, a tired officer filling out "
        "paperwork, grim fluorescent lighting"
    ),
    opciones=(
        Opcion(
            texto="Pedir que llamen a un abogado (te va a costar unos pesos)",
            destino="volver_al_hub",
            destino_alt="carcel_audiencia",
            prob_alt=0.3,
            dinero_delta={"pesos": -60},
            salud_delta=(-8, -2),
            mensaje_efecto="El abogado de guardia mueve un par de contactos y te saca antes de la audiencia.",
            item_favorable="documento de identidad",
            bonus_item_favorable=0.12,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.2,
        ),
        Opcion(
            texto="Intentar coimear al oficial de turno",
            destino="volver_al_hub",
            destino_alt="carcel_audiencia",
            prob_alt=0.55,
            dinero_delta={"pesos": -30},
            reputacion_delta=-5,
            salud_delta=(-8, -2),
            item_favorable="documento de identidad",
            bonus_item_favorable=0.1,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.15,
        ),
        Opcion(texto="Esperar tu turno sin hacer nada, a ver qué pasa", destino="carcel_audiencia"),
    ),
    destino_libre="carcel_audiencia",
))

_registrar(Nodo(
    id="carcel_audiencia",
    ubicacion="Comisaría del barrio, esperando audiencia",
    narracion=(
        "Te toca el turno frente a un fiscal que ya escuchó cuarenta casos "
        "iguales al tuyo esta misma noche. Todo va rapidísimo: nombre, "
        "cargos, una pregunta o dos. Nadie parece tener tiempo ni ganas de "
        "escuchar la historia completa de nadie."
    ),
    opciones=(
        Opcion(
            texto="Declarar que fue todo un malentendido y pedir que te dejen ir",
            destino="volver_al_hub",
            destino_alt="final_condenado",
            prob_alt=0.4,
            salud_delta=(-5, 0),
            item_favorable="documento de identidad",
            bonus_item_favorable=0.15,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.2,
        ),
        Opcion(
            texto="Aceptar un defensor oficial y confiar en que te vaya bien",
            destino="volver_al_hub",
            destino_alt="final_condenado",
            prob_alt=0.5,
            salud_delta=(-5, 0),
            item_favorable="documento de identidad",
            bonus_item_favorable=0.1,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.15,
        ),
        Opcion(
            texto="Quedarte en silencio, total ya está todo dicho",
            destino="volver_al_hub",
            destino_alt="final_condenado",
            prob_alt=0.6,
            salud_delta=(-5, 0),
            item_favorable="documento de identidad",
            bonus_item_favorable=0.08,
            condicion_desfavorable="sin_documento",
            penalizacion_condicion_desfavorable=0.1,
        ),
    ),
    destino_libre="final_condenado",
))

_registrar(Nodo(
    id="final_represion_piquete",
    ubicacion="Ruta despejada a la fuerza",
    narracion=(
        "La represión se llevó puesto el corte. Dispersaron a todos, se "
        "llevaron detenidos a varios compañeros, y en cuestión de minutos la "
        "ruta volvió a estar libre, como si el piquete nunca hubiera existido. "
        "Volvés a tu casa con las manos vacías y la garganta rota de gases, "
        "pensando en toda la gente que se quedó ahí, del otro lado de la "
        "topadora."
    ),
    imagen_en=(
        "the aftermath of a violently cleared highway roadblock at night, Buenos Aires "
        "December 2001, scattered burnt tires, police vehicles patrolling an empty road, "
        "a lone figure walking away defeated"
    ),
    es_final=True,
    final_tipo="represion_derrota",
))

_registrar(Nodo(
    id="final_condenado",
    ubicacion="Comisaría del barrio",
    narracion=(
        "No hay abogado, coima ni discurso que alcance: te dictan la "
        "prisión preventiva ahí mismo, en banda con otros diez casos de la "
        "misma noche. Che, ahora lo único que te queda es esperar que "
        "alguien allá afuera se acuerde de vos y que el expediente, algún "
        "día, se mueva."
    ),
    imagen_en=(
        "a somber scene of someone being led away into a holding cell at a crowded police "
        "station at night, Buenos Aires December 2001, grim fluorescent lighting, resigned "
        "expression"
    ),
    es_final=True,
    final_tipo="condenado",
))

_registrar(Nodo(
    id="final_presidente",
    ubicacion="Casa Rosada, Salón Blanco",
    narracion=(
        "Te sentás. El cuero del sillón todavía está tibio. Un asistente entra "
        "corriendo, te ve, y en vez de sacarte a los gritos te pregunta, "
        "agitado, si ya estás listo para el juramento — parece que, con la "
        "que está armada, nadie tuvo tiempo de fijarse bien quién sos. "
        "Afuera, alguien empieza a improvisar un discurso con tu nombre. En un "
        "país que va a tener cinco presidentes en dos semanas, uno más, uno "
        "menos, no le importa demasiado a nadie. Así, de pura casualidad y "
        "cara dura, terminaste siendo presidente de la Nación Argentina."
    ),
    imagen_en=(
        "a surreal and satirical scene of an ordinary person being sworn in as president in "
        "a grand government hall, improvised ceremony amid chaos, Casa Rosada, Buenos Aires "
        "December 2001, dramatic lighting, historic and absurd tone"
    ),
    es_final=True,
    final_tipo="presidente",
))


# ---------------------------------------------------------------------------
# 15. Comedor comunitario (sidequest)
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="comedor",
    ubicacion="Comedor comunitario, en el salón de una ex fábrica",
    narracion=(
        "El comedor funciona en lo que era el salón de una fábrica cerrada "
        "hace años. Ollas enormes, mesas de caballete, chicos comiendo antes "
        "que los grandes. Doña Rosa, que lo lleva casi sola, no para de "
        "moverse ni un segundo."
    ),
    dialogos=(
        (
            "Doña Rosa",
            "Si me hacés una changa, te guardo un plato bien servido, no seas malo. Necesito algo "
            "que se me perdió, y con este quilombo no puedo ir yo a buscarlo.",
        ),
    ),
    imagen_en=(
        "the inside of a community soup kitchen set up in a former factory "
        "hall, large cooking pots, long tables full of children and adults "
        "eating, a busy volunteer woman serving food"
    ),
    opciones=(
        Opcion(
            texto="Ofrecerte a hacerle el mandado que necesite",
            destino="comedor",
            excluye_flag="mision_comedor_activa",
            flags_add=("mision_comedor_activa",),
            mensaje_efecto=(
                "Doña Rosa te explica: dejó algo importante en el cibercafé antes de que "
                "empezara el quilombo, y no descarta que haya quedado tirado en el "
                "supermercado que saquearon. Andá a buscarlo donde puedas."
            ),
        ),
        Opcion(
            texto="Entregarle lo que conseguiste",
            destino="comedor",
            requiere_item="encargo de Doña Rosa",
            items_quitar=("encargo de Doña Rosa",),
            items_add=("bolsa de mercadería",),
            dinero_delta={"creditos_trueque": 15},
            reputacion_delta=10,
            flags_add=("mision_comedor_completa",),
            mensaje_efecto="Doña Rosa te abraza como si la hubieras sacado de un pozo.",
        ),
        Opcion(
            texto="Comer un plato de guiso, sin pedir nada a cambio",
            destino="volver_al_hub",
            salud_delta=(15, 25),
        ),
        Opcion(texto="Irte", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 15bis. Sustancias — alivio de corto plazo, con un precio
# ---------------------------------------------------------------------------
# `efecto_sustancia` es un nodo compartido: cualquier punto de entrada del
# guion puede mandar acá (hoy: bar_de_la_esquina, en el camino ambivalente/
# cartonero) y siempre ofrece la misma estructura de dos salidas —
# recomponerte y volver a la misión, o seguir en la joda y arriesgarte a
# terminar mal (final_perdido)—, sin necesidad de duplicar nodos por cada
# camino que lo dispare. `efecto_sustancia_piquete` es la variante narrativa
# para cuando la sustancia te la ofrecen en pleno piquete violento: ahí
# "volver a la misión" te devuelve al piquete en sí (piquetero_violento_2) en
# vez de al hub del barrio, porque la misión activa en ese momento es esa.

_registrar(Nodo(
    id="bar_de_la_esquina",
    ubicacion="El boliche de la esquina, con la persiana a medio bajar",
    narracion=(
        "El bar sigue abierto, no se sabe muy bien cómo. Hay un par de "
        "habitués tomando algo que no es exactamente café, y el dueño no te "
        "pregunta nada cuando le señalás la botella de atrás del mostrador. "
        "Con este quilombo, dice, ya nadie controla mucho nada."
    ),
    imagen_en=(
        "the inside of a small corner bar with a half-lowered metal shutter, a "
        "couple of regular patrons drinking at the counter, dim warm lighting, "
        "a bored bartender behind the bar"
    ),
    opciones=(
        Opcion(
            texto="Pedir una petaca de caña y tomártela de un saque",
            destino="efecto_sustancia",
            dinero_delta={"pesos": -5},
            items_add=("una petaca de caña",),
        ),
        Opcion(
            texto="Comprarle a un habitué un cigarrillo de marihuana",
            destino="efecto_sustancia",
            dinero_delta={"pesos": -10},
            items_add=("un cigarrillo de marihuana",),
        ),
        Opcion(
            texto="Pedirle al dueño una pastilla para los nervios que sabe vender bajo mano",
            destino="efecto_sustancia",
            dinero_delta={"pesos": -15},
            items_add=("una pastilla para los nervios",),
        ),
        Opcion(texto="Tomar solo un café y seguir con lo tuyo", destino="volver_al_hub", salud_delta=(2, 6)),
        Opcion(texto="Irte, no es momento para esto", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="efecto_sustancia",
    ubicacion="Un rato después, en algún lado que ya no ubicás del todo bien",
    narracion=(
        "Por un rato, el quilombo de afuera se apaga. Las voces se escuchan "
        "como de lejos, los bordes de las cosas se ponen raros. Se siente "
        "bien, mientras dura. El problema es que, cuando empieza a bajar el "
        "efecto, todo lo que dejaste en pausa —el objetivo, la plata, la "
        "gente que te espera— sigue ahí, esperando que vuelvas."
    ),
    opciones=(
        Opcion(
            texto="Recomponerte como puedas y volver a lo tuyo",
            destino="volver_al_hub",
            salud_delta=(-10, -3),
        ),
        Opcion(
            texto="Seguir en la joda un rato más, totalmente da igual",
            destino="volver_al_hub",
            destino_alt="final_perdido",
            prob_alt=0.35,
            salud_delta=(-20, -8),
            alineacion_delta=-5,
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="efecto_sustancia_piquete",
    ubicacion="En medio del piquete, con la cabeza en otro lado",
    narracion=(
        "El pibe te mira fijo mientras te la ofrece: \"tomá, así aguantás\". "
        "La tomás sin pensar mucho. Por un rato el miedo desaparece del todo "
        "—el ruido de los gases, los caballos, todo se siente lejano, casi "
        "como si le pasara a otro—. Pero la cabeza te empieza a jugar en "
        "contra: ya no tenés muy claro cuánto tiempo pasó, ni bien qué está "
        "pasando alrededor tuyo."
    ),
    opciones=(
        Opcion(
            texto="Sacudirte el efecto y volver a meterte en el piquete",
            destino="piquetero_violento_2",
            salud_delta=(-12, -4),
        ),
        Opcion(
            texto="Quedarte perdido en el humo, sin fuerzas para nada más",
            destino="volver_al_hub",
            destino_alt="final_perdido",
            prob_alt=0.45,
            salud_delta=(-25, -10),
            alineacion_delta=-5,
        ),
    ),
    destino_libre="piquetero_violento_2",
    capitulo=3,
))


# ---------------------------------------------------------------------------
# 16. Economía: hospital y mercado negro
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="hospital",
    ubicacion="Guardia del hospital público",
    narracion=(
        "La guardia está desbordada: sillas ocupadas, gente sentada en el "
        "piso, un pibe con la cabeza vendada de cualquier manera. Huele a "
        "alcohol en gel y a cansancio. Una enfermera hace lo que puede con lo "
        "que hay, que no es mucho."
    ),
    imagen_en=(
        "an overcrowded public hospital emergency room at night, people sitting "
        "on chairs and on the floor waiting, an exhausted nurse attending a "
        "patient, fluorescent lighting"
    ),
    opciones=(
        Opcion(
            texto="Pagar una consulta privada rápida, para no esperar",
            destino="volver_al_hub",
            dinero_delta={"pesos": -25},
            salud_delta=(25, 35),
            mensaje_efecto="Con unos pesos de más, todo se mueve más rápido en cualquier lado.",
        ),
        Opcion(
            texto="Esperar tu turno en la guardia pública, gratis",
            destino="volver_al_hub",
            salud_delta=(8, 16),
        ),
        Opcion(texto="Irte, no tenés tiempo para esperar", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="camino_mercado_negro",
    ubicacion="Callejones detrás del club de trueque",
    narracion=(
        "Un pibe que conoce a alguien te lleva por un pasillo entre casas, "
        "después un descampado sin luz, después una casa sin cartel ni "
        "timbre. El corazón se te acelera: esto no es ninguna joda, y no hay "
        "vuelta atrás fácil una vez que empezás a caminar."
    ),
    opciones=(
        Opcion(
            texto="Seguir adelante, ya estás metido en esto",
            destino="mercado_negro",
            destino_alt="asalto_callejero",
            prob_alt=0.2,
        ),
        Opcion(
            texto="Esperar en la esquina a que el pibe confirme que es seguro entrar",
            destino="mercado_negro",
            destino_alt="mercado_negro_tiempo_perdido",
            prob_alt=0.7,
            salud_delta=(-3, 1),
        ),
        Opcion(texto="Arrepentirte y volver, esto es una locura", destino="volver_al_hub"),
    ),
    destino_libre="mercado_negro",
))

_registrar(Nodo(
    id="mercado_negro_tiempo_perdido",
    ubicacion="La misma esquina, mucho más tarde de lo planeado",
    narracion=(
        "El \"pibe\" nunca vuelve a confirmar nada. Esperás una hora, después "
        "dos, hasta que se hace de noche cerrada y entendés que hoy no hay "
        "reducidor que valga. Volver mañana con las manos vacías significa "
        "perder el resto del día en otra cosa que no era lo que tenías "
        "planeado."
    ),
    opciones=(
        Opcion(
            texto="Volver mañana y seguir con lo que quede del día",
            destino="avanzar_capitulo",
            salud_delta=(-5, -1),
            alineacion_delta=-3,
        ),
    ),
    destino_libre="avanzar_capitulo",
))

_registrar(Nodo(
    id="mercado_negro",
    ubicacion="Una casa sin cartel, en algún lado del conurbano",
    narracion=(
        "Adentro, un tipo que no te mira a los ojos revisa lo que llevás "
        "encima con una linterna. No pregunta de dónde salió nada, y vos "
        "tampoco preguntás nada de él. Todo acá se paga en pesos, al "
        "contado, y a un precio que no vas a poder discutir."
    ),
    dialogos=(
        ("El reducidor", "Acá no hay factura ni devolución, así que pensalo bien antes de ofrecer algo."),
    ),
    imagen_en=(
        "a shadowy figure examining stolen goods by flashlight inside a dim unmarked house, "
        "a black market fence scene in a Buenos Aires suburb in December 2001, tense and "
        "secretive atmosphere"
    ),
    opciones=(
        Opcion(
            texto="Vender el televisor chico que tenés",
            destino="mercado_negro",
            requiere_item="un televisor chico",
            items_quitar=("un televisor chico",),
            dinero_delta={"pesos": 25},
            mensaje_efecto="Te paga bastante menos de lo que vale, pero no estás en condiciones de negociar.",
        ),
        Opcion(
            texto="Vender el cuadro afanado de la Casa Rosada",
            destino="mercado_negro",
            requiere_item="un cuadro chico afanado de la Casa Rosada",
            items_quitar=("un cuadro chico afanado de la Casa Rosada",),
            dinero_delta={"pesos": 80},
            mensaje_efecto="El tipo silba por lo bajo cuando lo ve. \"Esto sí que es raro\", dice, y paga sin discutir.",
        ),
        Opcion(
            texto="Comprarle una bolsa de mercadería a sobreprecio",
            destino="mercado_negro",
            dinero_delta={"pesos": -15},
            items_add=("bolsa de mercadería",),
        ),
        Opcion(texto="Irte de ahí cuanto antes, este lugar te da mala espina", destino="volver_al_hub"),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 17. Eventos ambientales del camino
# ---------------------------------------------------------------------------
# No siempre tienen un nodo que "lleva" hasta acá: game/engine.py también
# puede redirigir al azar hacia estos nodos al entrar a la esquina del
# barrio, simulando que en cualquier viaje por el conurbano te puede pasar
# algo sin que lo hayas elegido.

_registrar(Nodo(
    id="asalto_callejero",
    ubicacion="Un pasillo oscuro, en algún lado del camino",
    narracion=(
        "Dos tipos te cierran el paso. Uno te muestra algo brillante en la "
        "cintura, no queda claro si es un arma de verdad o un bluff, y no "
        "vas a quedarte a averiguarlo. \"Dejá todo y no pasa nada\", te dice, "
        "con una calma que da más miedo que si gritara."
    ),
    imagen_en=(
        "a tense mugging scene in a dark narrow alley in a Buenos Aires suburb at night, "
        "two menacing figures blocking a person's path, December 2001, gritty and dangerous "
        "atmosphere"
    ),
    opciones=(
        Opcion(
            texto="Entregar lo que tenés encima sin discutir",
            destino="volver_al_hub",
            dinero_delta={"pesos": -999, "patacones": -999, "lecops": -999},
            reputacion_delta=-1,
            roba_item_aleatorio=True,
            mensaje_efecto="Te vacían los bolsillos y se van caminando tranquilos, como si nada.",
            reputacion_minima_favorable=15,
            bonus_salud_reputacion=5,
        ),
        Opcion(
            texto="Correr antes de que reaccionen",
            destino="volver_al_hub",
            destino_alt="volver_al_hub",
            salud_delta=(-15, -3),
            reputacion_minima_favorable=15,
            bonus_salud_reputacion=8,
        ),
        Opcion(
            texto="Resistirte y no soltar tus cosas",
            destino="volver_al_hub",
            salud_delta=(-30, -12),
            reputacion_minima_favorable=15,
            bonus_salud_reputacion=15,
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="atrapado_manifestacion",
    ubicacion="En medio de una manifestación que no era la tuya",
    narracion=(
        "Doblás en una esquina y quedás en medio de una columna de gente "
        "marchando con bombos y banderas que ni sabés de qué agrupación son. "
        "Antes de que puedas salir del medio, la marcha se cierra a tu "
        "alrededor: para bien o para mal, ahora sos parte de esto."
    ),
    imagen_en=(
        "a person unexpectedly caught in the middle of a large street march with flags and "
        "drums in Buenos Aires, December 2001, dense crowd, dusk light, documentary "
        "photojournalism framing"
    ),
    opciones=(
        Opcion(
            texto="Dejarte llevar por la marcha hasta que puedas salir",
            destino="volver_al_hub",
            salud_delta=(-5, 2),
        ),
        Opcion(
            texto="Abrirte paso a los codazos para salir cuanto antes",
            destino="volver_al_hub",
            salud_delta=(-10, -2),
            reputacion_delta=-2,
        ),
        Opcion(
            texto="Aprovechar y sumarte a los cánticos, ya que estás",
            destino="volver_al_hub",
            reputacion_delta=3,
        ),
    ),
    destino_libre="volver_al_hub",
))


# ---------------------------------------------------------------------------
# 17bis. Demoras de transporte — el "mapa mental" del GBA hecho evento
# ---------------------------------------------------------------------------
# Mismo mecanismo que asalto_callejero/atrapado_manifestacion (evento
# ambiental al volver a un hub), pero acá la variante depende de la zona del
# GBA/CABA de la que sale el personaje (game/engine.py:
# DEMORA_TRANSPORTE_POR_ZONA) — el Sarmiento, el Mitre y el Roca eran, ya en
# 2001, sinónimo de línea de tren específica con fama propia; en CABA el
# problema es otro (subte/colectivo saturado), no un tren de larga distancia.

_registrar(Nodo(
    id="demora_transporte_caba",
    ubicacion="Boca de subte, hora pico",
    narracion=(
        "La línea de subte que ibas a tomar para cuando llegás. \"Demorado por "
        "inconvenientes técnicos\", dice el cartel de siempre, sin más detalle. "
        "Arriba, en la calle, el colectivo que podría reemplazarlo pasa de largo "
        "tres veces seguidas, repleto hasta la puerta."
    ),
    opciones=(
        Opcion(
            texto="Esperar a que se solucione, total no hay apuro que valga",
            destino="volver_al_hub",
            salud_delta=(-3, 1),
        ),
        Opcion(
            texto="Ir caminando el resto, con este calor y todo",
            destino="volver_al_hub",
            salud_delta=(-8, -3),
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="demora_transporte_zona_norte",
    ubicacion="Andén del Mitre, esperando que salga algo",
    narracion=(
        "El tren Mitre acumula ya una hora larga de demora por un problema de "
        "señales en Retiro, según dice un guarda que tampoco parece muy seguro. "
        "El andén se va llenando de gente que mira el reloj y putea bajito, "
        "todos con el mismo problema que vos."
    ),
    opciones=(
        Opcion(
            texto="Aguantar en el andén hasta que salga el tren",
            destino="volver_al_hub",
            salud_delta=(-5, 0),
        ),
        Opcion(
            texto="Buscar un colectivo que haga el mismo recorrido, más lento pero seguro",
            destino="volver_al_hub",
            salud_delta=(-8, -2),
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="demora_transporte_zona_oeste",
    ubicacion="Andén del Sarmiento, altura Ramos Mejía",
    narracion=(
        "El Sarmiento está parado a la altura de Ramos Mejía, dicen que por una "
        "protesta sobre las vías más adelante. No es la primera vez esta semana, "
        "y todo el mundo en el andén lo sabe: alguien ya sacó un mate para "
        "aguantar la espera con algo de dignidad."
    ),
    opciones=(
        Opcion(
            texto="Aguantar en el andén hasta que se destranque",
            destino="volver_al_hub",
            salud_delta=(-6, 0),
        ),
        Opcion(
            texto="Cruzar a buscar un colectivo, aunque te deje lejos de donde ibas",
            destino="volver_al_hub",
            salud_delta=(-10, -3),
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="demora_transporte_zona_sur",
    ubicacion="Andén del Roca, mirando las vías vacías",
    narracion=(
        "El Roca vuelve a acumular demoras homéricas: hablan de un choque más "
        "adelante en las vías, o de un problema eléctrico, según a quién le "
        "preguntes. Las vías están vacías a pérdida de vista, sin un solo tren "
        "asomando."
    ),
    opciones=(
        Opcion(
            texto="Esperar en el andén, no queda otra",
            destino="volver_al_hub",
            salud_delta=(-5, 0),
        ),
        Opcion(
            texto="Rebuscártela con un colectivo o un remis compartido",
            destino="volver_al_hub",
            salud_delta=(-8, -2),
            dinero_delta={"pesos": -5},
        ),
    ),
    destino_libre="volver_al_hub",
))

_registrar(Nodo(
    id="demora_transporte_generico",
    ubicacion="Parada de colectivo, esperando hace rato",
    narracion=(
        "El colectivo que estás esperando no aparece hace más de cuarenta "
        "minutos: puede ser el paro de otra línea, puede ser un corte más allá, "
        "puede ser directamente que no viene. En la parada ya se juntó un grupo "
        "grande esperando lo mismo que vos."
    ),
    opciones=(
        Opcion(
            texto="Seguir esperando, no hay mucha otra opción",
            destino="volver_al_hub",
            salud_delta=(-5, 0),
        ),
        Opcion(
            texto="Empezar a caminar, aunque te quede lejos",
            destino="volver_al_hub",
            salud_delta=(-8, -3),
        ),
    ),
    destino_libre="volver_al_hub",
))


def existe_nodo(nodo_id: str) -> bool:
    return nodo_id in NODOS


def obtener_nodo(nodo_id: str) -> Nodo:
    return NODOS[nodo_id]
