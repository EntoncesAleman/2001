"""Grafo narrativo del RPG "Argentina 2001".

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

    flags_add: Tuple[str, ...] = ()
    flags_quitar: Tuple[str, ...] = ()
    items_add: Tuple[str, ...] = ()
    items_quitar: Tuple[str, ...] = ()
    estados_add: Tuple[str, ...] = ()
    estados_quitar: Tuple[str, ...] = ()

    requiere_flag: Optional[str] = None
    requiere_item: Optional[str] = None
    excluye_flag: Optional[str] = None

    destino_alt: Optional[str] = None
    prob_alt: float = 0.0

    mensaje_efecto: str = ""


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


NODOS: Dict[str, Nodo] = {}


def _registrar(nodo: Nodo) -> None:
    NODOS[nodo.id] = nodo


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
        Opcion(texto="Acercarte a la asamblea que se está armando en la placita", destino="asamblea_barrial"),
        Opcion(texto="Ir al club de trueque a ver qué conseguís para comer", destino="club_trueque"),
        Opcion(texto="Pasar por el cibercafé a ver si hay noticias o mensajes", destino="cibercafe"),
    ),
    destino_libre="esquina_barrio",
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
    dialogos=(
        ("Señor de traje", "Yo laburé treinta años para esto, pibe. Treinta años."),
    ),
    opciones=(
        Opcion(texto="Esperar tu turno con paciencia, como todos", destino="banco_espera",
               salud_delta=(-4, -1)),
        Opcion(texto="Acercarte al guardia de la puerta a ver si por izquierda se puede algo", destino="banco_soborno",
               requiere_item=None),
        Opcion(texto="Sumarte a la gente que empieza a golpear las rejas y putear", destino="banco_protesta"),
        Opcion(texto="Rajar de la fila, esto no va a ningún lado", destino="esquina_barrio"),
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
        Opcion(texto="Salir rápido y perderte entre la gente", destino="esquina_barrio",
               dinero_delta={"pesos": 60}, flags_add=("objetivo_cumplido_plata",)),
        Opcion(texto="Ir directo al club de trueque a hacer rendir esa plata", destino="club_trueque",
               dinero_delta={"pesos": 60}, flags_add=("objetivo_cumplido_plata",)),
    ),
    destino_libre="esquina_barrio",
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
            destino="esquina_barrio",
            destino_alt="represion",
            prob_alt=0.3,
        ),
        Opcion(
            texto="Proponerle a la gente cercana organizarse en asamblea en vez de gritar solos",
            destino="asamblea_barrial",
            reputacion_delta=5,
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
            destino="esquina_barrio",
            salud_delta=(-25, -8),
            estados_add=("tos por gases",),
        ),
        Opcion(
            texto="Parar a levantar al vecino caído aunque te arriesgues",
            destino="esquina_barrio",
            destino_alt="represion_herido",
            prob_alt=0.45,
            salud_delta=(-15, -5),
            reputacion_delta=12,
            flags_add=("ayudaste_en_represion",),
            estados_add=("tos por gases",),
        ),
        Opcion(
            texto="Plantarte de espaldas a una pared y esperar a que pase la corrida",
            destino="esquina_barrio",
            salud_delta=(-35, -10),
            estados_add=("tos por gases", "agitado"),
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
        Opcion(texto="Agradecer y quedarte ahí escondido hasta que amaine", destino="esquina_barrio",
               reputacion_delta=3),
        Opcion(texto="Salir igual, apenas termine la corrida, a buscar a los tuyos", destino="esquina_barrio",
               salud_delta=(-10, -3)),
    ),
    destino_libre="esquina_barrio",
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
        Opcion(texto="Retirarte, esto no es lo tuyo", destino="esquina_barrio"),
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
        Opcion(texto="Volver a tu casa a descansar, mañana es otro día largo", destino="esquina_barrio",
               salud_delta=(5, 12)),
        Opcion(texto="Quedarte a dormir en la placita, cuidando entre todos por si vuelve la cana", destino="calle_noche",
               flags_add=("noche_en_asamblea",), reputacion_delta=5),
    ),
    destino_libre="esquina_barrio",
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
    dialogos=(
        ("Coordinadora del club", "Acá nadie te va a garcar con la cotización, che. Un crédito es un crédito."),
    ),
    opciones=(
        Opcion(texto="Cambiar parte de tus Patacones/Lecops por créditos de trueque", destino="club_trueque_intercambio",
               dinero_delta={"patacones": 0}),
        Opcion(texto="Ofrecer algo de tu inventario a cambio de comida", destino="club_trueque_intercambio"),
        Opcion(texto="Quedarte charlando para enterarte de rumores del barrio", destino="club_trueque_intercambio",
               reputacion_delta=2),
        Opcion(texto="Irte, esto no te resuelve nada hoy", destino="esquina_barrio"),
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
        Opcion(texto="Volver a tu barrio con la mercadería conseguida", destino="esquina_barrio",
               dinero_delta={"creditos_trueque": 10, "patacones": -5}, items_add=("bolsa de mercadería",)),
        Opcion(texto="Pasar por la asamblea a aportar parte de lo conseguido", destino="asamblea_barrial",
               dinero_delta={"creditos_trueque": 5}, items_add=("bolsa de mercadería",), reputacion_delta=6),
    ),
    destino_libre="esquina_barrio",
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
    opciones=(
        Opcion(texto="Revisar si hay algún mail o mensaje de gente conocida", destino="cibercafe_noticia"),
        Opcion(texto="Quedarte mirando las noticias en la tele para saber qué está pasando", destino="cibercafe_noticia",
               reputacion_delta=1),
        Opcion(texto="Salir, esto no te sirve de mucho ahora", destino="esquina_barrio"),
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
        Opcion(texto="Volver a tu barrio, es muy arriesgado ir para allá solo", destino="esquina_barrio"),
        Opcion(texto="Ir a la asamblea a pedir ayuda para buscar", destino="asamblea_barrial",
               reputacion_delta=2),
    ),
    destino_libre="esquina_barrio",
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
        ),
        Opcion(
            texto="Ayudar al dueño a defender la puerta en vez de robar",
            destino="saqueo_ayudar_dueno",
        ),
        Opcion(
            texto="Buscar entre la gente si reconocés a la persona que estás buscando",
            destino="calle_noche",
            requiere_flag="buscando_familiar",
            destino_alt="calle_noche",
        ),
        Opcion(texto="Rajar de ahí, esto se puede poner muy feo", destino="esquina_barrio",
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
            destino="esquina_barrio",
            destino_alt="represion",
            prob_alt=0.35,
            items_add=("bolsa de mercadería",),
            reputacion_delta=-3,
        ),
        Opcion(
            texto="Quedarte cargando todo lo que puedas, total ya estás adentro",
            destino="esquina_barrio",
            destino_alt="represion",
            prob_alt=0.6,
            items_add=("bolsa de mercadería", "un televisor chico"),
            reputacion_delta=-10,
            salud_delta=(-10, 0),
        ),
    ),
    destino_libre="esquina_barrio",
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
            destino="esquina_barrio",
            salud_delta=(-15, -4),
            reputacion_delta=10,
            flags_add=("defendiste_comercio",),
            items_add=("agradecimiento del dueño: bolsa de mercadería",),
        ),
        Opcion(
            texto="Irte apenas baja la tensión, ya hiciste lo que pudiste",
            destino="esquina_barrio",
            salud_delta=(-8, -2),
            reputacion_delta=6,
        ),
    ),
    destino_libre="esquina_barrio",
))


# ---------------------------------------------------------------------------
# 8. Hub nocturno (previo a los finales)
# ---------------------------------------------------------------------------

_registrar(Nodo(
    id="calle_noche",
    ubicacion="Tu barrio, ya de noche",
    narracion=(
        "Cae la noche sobre un Gran Buenos Aires que no se parece en nada al de "
        "hace una semana. A lo lejos siguen las cacerolas, más cansadas ahora, "
        "casi un arrullo triste. Tenés que decidir qué hacer con lo que te "
        "queda de fuerzas y de día."
    ),
    salud_entrada=(-2, 1),
    opciones=(
        Opcion(texto="Volver a tu casa a descansar y esperar que amanezca", destino="final_decision",
               salud_delta=(3, 8)),
        Opcion(texto="Tomar la decisión de irte del Conurbano/CABA en cuanto puedas", destino="final_decision",
               flags_add=("decidio_huir",)),
        Opcion(texto="Quedarte en la calle, con los vecinos, pase lo que pase", destino="final_decision",
               reputacion_delta=6),
    ),
    destino_libre="final_decision",
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
        "background, bittersweet cinematic lighting, pixel art adventure game ending scene"
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
        "of solidarity amid the crisis, pixel art adventure game ending illustration"
    ),
    es_final=True,
    final_tipo="comunidad",
))

_registrar(Nodo(
    id="final_huida",
    ubicacion="Ruta hacia afuera del Conurbano",
    narracion=(
        "Juntaste lo poco que te quedaba y decidiste que este no iba a ser tu "
        "final. Dejás atrás el barrio, el banco, la asamblea, el ruido de las "
        "cacerolas cada vez más lejano por el espejo retrovisor. No sabés bien "
        "qué te espera del otro lado, pero por primera vez en días, el pecho se "
        "te afloja un poco."
    ),
    imagen_en=(
        "a lone figure walking away on a highway leaving Greater Buenos Aires at dawn, "
        "December 2001, looking back at the city skyline with smoke rising in the distance, "
        "a sense of uncertain hope, pixel art adventure game ending illustration"
    ),
    es_final=True,
    final_tipo="huida",
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
        "quiet and isolated mood, pixel art adventure game ending illustration"
    ),
    es_final=True,
    final_tipo="solitario",
))


def existe_nodo(nodo_id: str) -> bool:
    return nodo_id in NODOS


def obtener_nodo(nodo_id: str) -> Nodo:
    return NODOS[nodo_id]
