"""Estado del jugador: ubicación, salud, inventario, dinero y flags de historia."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple


# Etiqueta legible de cada capítulo (usado como "día" en el HUD, en ambos
# modos): le da al jugador una referencia de progreso sin exponer números de
# nodo internos. Compartido por game/engine.py, game/modo_libre.py, main.py y
# el frontend web.
CAPITULO_LABEL: Dict[int, str] = {
    1: "Días previos al estallido",
    2: "Noche del 19 de diciembre",
    3: "20 de diciembre — el día del estallido",
    4: "La semana de los presidentes (Puerta)",
    5: "La semana de los presidentes (Rodríguez Saá)",
    6: "La semana de los presidentes (Duhalde)",
    7: "El cierre",
}
CAPITULOS_TOTALES = 7

# Flags/hitos narrativamente relevantes que vale la pena resumir al final de
# la partida (pantalla de estadísticas). No es una lista exhaustiva de todos
# los flags del juego, solo los que cuentan algo sobre CÓMO se jugó.
HITOS_DESCRIPCION: Dict[str, str] = {
    "ayudaste_en_represion": "Ayudaste a alguien caído en medio de una represión",
    "defendiste_comercio": "Defendiste un comercio de un saqueo",
    "trabajaste_de_cartonero": "Te subiste al tren de los cartoneros a juntar cartón",
    "mision_comedor_completa": "Completaste el mandado de Doña Rosa",
    "mision_comedor_fallida": "Dejaste colgado el mandado de Doña Rosa",
    "tiraste_molotov": "Tiraste una bomba molotov en un piquete",
    "zafaste_de_la_cana": "Te zafaste de la policía a las piñas",
    "salvaste_a_alguien": "Salvaste a un compañero herido en la represión",
    "resististe_hasta_el_final": "Resististe hasta el final en la represión",
    "sin_documento": "Perdiste tu documento de identidad en el camino",
    "corte_ruta_ajena": "Te sumaste a cortar una ruta en un barrio que no era el tuyo",
    "perdiste_un_dia": "Perdiste un día entero lejos de tu casa",
}


# Puntaje base según cómo termina la partida: no mide "qué tan legal o
# ilegal jugaste" (eso ya lo describe "camino"), mide qué tan bien te fue.
# Los finales de derrota clara puntúan negativo; los de objetivo logrado o
# los easter eggs/logros difíciles puntúan fuerte en positivo; "solitario"
# (sobrevivir sin más) es el punto neutro de referencia.
FINAL_PUNTAJE_BONUS: Dict[str, int] = {
    "objetivo_cumplido": 100,
    "comunidad": 80,
    "referente_piquetero": 150,
    "presidente": 250,
    "solitario": 0,
    "cartonero": -30,
    "condenado": -50,
    "represion_derrota": -50,
    "perdido": -60,
    "muerte": -120,
    "muerte_manifestacion": -120,
}


def resumen_camino(alineacion: int) -> str:
    """Etiqueta del "camino" según el eje legal/ilegal acumulado."""
    if alineacion <= -35:
        return "fuera de la ley"
    if alineacion >= 35:
        return "dentro de la ley"
    return "ambivalente"


@dataclass
class Dinero:
    """Las tres (o cuatro) formas de "plata" que circulaban en diciembre de 2001."""

    pesos: int = 0
    patacones: int = 0
    lecops: int = 0
    creditos_trueque: int = 0

    def describir(self) -> str:
        partes: List[str] = []
        if self.pesos:
            partes.append(f"${self.pesos} pesos")
        if self.patacones:
            partes.append(f"{self.patacones} Patacones")
        if self.lecops:
            partes.append(f"{self.lecops} Lecops")
        if self.creditos_trueque:
            partes.append(f"{self.creditos_trueque} créditos de trueque")
        return ", ".join(partes) if partes else "ni un mango"

    def aplicar(self, delta: Dict[str, int]) -> None:
        for clave, valor in delta.items():
            if not hasattr(self, clave):
                continue
            nuevo = getattr(self, clave) + valor
            setattr(self, clave, max(0, nuevo))

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @staticmethod
    def from_dict(datos: Dict[str, int]) -> "Dinero":
        return Dinero(
            pesos=datos.get("pesos", 0),
            patacones=datos.get("patacones", 0),
            lecops=datos.get("lecops", 0),
            creditos_trueque=datos.get("creditos_trueque", 0),
        )


# Categorías generales que se usan para reconocer el objetivo elegido por el
# jugador (texto libre) y saber, más adelante en la historia, si lo cumplió.
# El orden importa: se evalúan de arriba a abajo y gana la primera que
# matchee, así que las frases más específicas van primero (evita que
# "negocio familiar" se detecte como "familiar" en vez de "negocio").
CATEGORIAS_OBJETIVO = (
    ("negocio", ("negocio", "local", "comercio", "kiosco", "taller", "changa", "laburo", "trabajo")),
    ("plata", ("ahorro", "banco", "plata", "guita", "dinero", "cuenta", "retirar", "corralito")),
    ("escape", ("escapar", "huir", "irme", "salir del pais", "cruzar", "frontera", "afuera")),
    ("familiar", ("hermano", "hermana", "madre", "padre", "hijo", "hija", "abuel", "buscar a", "mi familia", "un familiar")),
)


def detectar_categoria_objetivo(texto: str) -> str:
    texto_bajo = texto.lower()
    for categoria, palabras_clave in CATEGORIAS_OBJETIVO:
        if any(palabra in texto_bajo for palabra in palabras_clave):
            return categoria
    return "generico"


# "Mapa mental" del Gran Buenos Aires y CABA: de qué barrio sale el
# personaje determina qué tren/transporte usa y cuánto le come el día viajar
# — no es solo color, ver ZONA_INFO y game/engine.py (_limite_cansancio,
# DEMORA_TRANSPORTE_POR_ZONA). El orden importa por el mismo motivo que
# CATEGORIAS_OBJETIVO: lo más específico primero.
ZONAS_GBA = (
    (
        "caba",
        (
            "caba", "capital federal", "microcentro", "recoleta", "palermo", "once",
            "flores", "almagro", "boedo", "caballito", "belgrano", "villa urquiza",
            "constitucion", "constitución", "retiro", "la boca", "barracas",
            "mataderos", "liniers", "nuñez", "núñez", "chacarita", "colegiales",
        ),
    ),
    (
        "zona_norte",
        (
            "tigre", "san isidro", "vicente lopez", "vicente lópez", "san fernando",
            "olivos", "martinez", "martínez", "pilar", "escobar", "san miguel",
            "jose c paz", "josé c paz", "malvinas argentinas", "boulogne",
        ),
    ),
    (
        "zona_oeste",
        (
            "la matanza", "moron", "morón", "hurlingham", "ituzaingo", "ituzaingó",
            "merlo", "moreno", "general rodriguez", "general rodríguez", "san justo",
            "ramos mejia", "ramos mejía", "castelar", "haedo", "gregorio de laferrere",
            "ciudad evita", "isidro casanova",
        ),
    ),
    (
        "zona_sur",
        (
            "lomas de zamora", "avellaneda", "quilmes", "lanus", "lanús",
            "berazategui", "florencio varela", "almirante brown", "ezeiza",
            "esteban echeverria", "esteban echeverría", "banfield", "temperley",
            "adrogue", "adrogué", "wilde", "sarandi", "sarandí",
        ),
    ),
)

# Info real de transporte de cada zona: qué tren la conecta con CABA (o si se
# mueve en subte/colectivo, como en CABA misma) y cuánto le resta al margen
# del día viajar desde ahí (ver engine.py:_limite_cansancio). El Sarmiento
# era, ya en 2001, el ejemplo de tren colapsado/impredecible del Oeste — por
# eso zona_oeste tiene el ajuste más negativo.
ZONA_INFO: Dict[str, Dict[str, Any]] = {
    "caba": {"transporte": "colectivo y subte", "ajuste_cansancio": 2},
    "zona_norte": {"transporte": "el tren Mitre", "ajuste_cansancio": -1},
    "zona_oeste": {"transporte": "el tren Sarmiento", "ajuste_cansancio": -2},
    "zona_sur": {"transporte": "el tren Roca", "ajuste_cansancio": -1},
    "conurbano_generico": {"transporte": "colectivo", "ajuste_cansancio": 0},
}


def detectar_zona_gba(texto: str) -> str:
    texto_bajo = texto.lower()
    for zona, palabras_clave in ZONAS_GBA:
        if any(palabra in texto_bajo for palabra in palabras_clave):
            return zona
    return "conurbano_generico"


@dataclass
class EstadoJugador:
    nombre: str
    trasfondo: str
    barrio_inicial: str
    objetivo: str
    objetivo_categoria: str = "generico"
    # Zona del Gran Buenos Aires/CABA de la que sale el personaje, detectada
    # de barrio_inicial (ver detectar_zona_gba arriba). Afecta cuánto le
    # rinde el día (game/engine.py:_limite_cansancio) y qué evento de demora
    # de transporte le puede tocar (DEMORA_TRANSPORTE_POR_ZONA).
    zona_gba: str = "conurbano_generico"

    nodo_actual: str = "esquina_barrio"
    ubicacion: str = ""

    salud: int = 100
    estados: Set[str] = field(default_factory=set)
    inventario: List[str] = field(default_factory=list)
    dinero: Dinero = field(default_factory=Dinero)
    flags: Set[str] = field(default_factory=set)
    reputacion_barrial: int = 0

    # Eje "legal / ilegal" (-100..100): negativo = camino fuera de la ley,
    # positivo = dentro de la ley, cerca de 0 = ambivalente. Es independiente
    # de reputacion_barrial (podés tener buena onda con el barrio y aun así
    # estar metido en quilombos ilegales, o ser un modelo de ciudadano
    # antipático con nadie).
    alineacion: int = 0

    # Capítulo actual de la campaña (1 = días previos ... 7 = cierre). Lo
    # actualiza game/engine.py al entrar a un nodo que define `capitulo`;
    # sirve para que los nodos de servicio (hospital, trueque, etc.) sepan a
    # qué hub volver sin tener que duplicarse por capítulo.
    capitulo: int = 1

    turno: int = 0
    vivo: bool = True
    ultima_imagen_url: str = ""

    # Orden en el que se muestran las opciones del nodo actual (una
    # permutación de índices sobre game/story.py:Nodo.opciones). Se
    # recalcula cada vez que se entra a un nodo nuevo (game/engine.py) para
    # que aprenderse "1, 3, 2" de memoria no sirva de nada en la próxima
    # partida ni en una segunda vuelta por el mismo nodo.
    orden_opciones: List[int] = field(default_factory=list)

    # Turno en el que se aceptó el mandado de Doña Rosa (comedor comunitario).
    # None si nunca se aceptó o ya se resolvió (entregado o vencido). Sirve
    # para que la misión no quede "colgada" para siempre — ver
    # game/engine.py:_chequear_vencimiento_comedor.
    turno_mision_comedor: Optional[int] = None

    # Conjunto de ubicaciones (Nodo.ubicacion en modo historia, estado.ubicacion
    # en modo libre) distintas por las que pasó el personaje. Sirve solo para
    # la pantalla de estadísticas finales ("cuántos lugares distintos
    # recorriste"), no afecta la mecánica del juego.
    lugares_visitados: Set[str] = field(default_factory=set)

    # --- Solo se usan en modo "libre" (game/modo_libre.py) -----------------
    # En modo "historia" la fuente de verdad es el grafo de game/story.py
    # (nodo_actual); en modo "libre" no hay grafo fijo, así que la escena, las
    # opciones y el desenlace los guarda el LLM turno a turno directamente acá.
    modo: str = "historia"
    escena_libre: str = ""
    dialogos_libres: List[Tuple[str, str]] = field(default_factory=list)
    opciones_libres: List[str] = field(default_factory=list)
    historial_libre: List[Dict[str, str]] = field(default_factory=list)
    es_final_libre: bool = False
    final_tipo_libre: Optional[str] = None

    def salud_clamp(self) -> None:
        self.salud = max(0, min(100, self.salud))
        if self.salud <= 0:
            self.vivo = False

    def descripcion_salud(self) -> str:
        if not self.vivo:
            return "sin vida"
        if self.salud >= 85:
            partes = ["en buen estado"]
        elif self.salud >= 60:
            partes = ["cansado"]
        elif self.salud >= 35:
            partes = ["golpeado", "al límite"]
        else:
            partes = ["muy mal herido"]
        if self.estados:
            partes.extend(sorted(self.estados))
        return ", ".join(partes)

    def descripcion_inventario(self) -> str:
        cosas = ", ".join(self.inventario) if self.inventario else "los bolsillos vacíos"
        plata = self.dinero.describir()
        return f"{cosas} — {plata}"

    def etiqueta_capitulo(self) -> str:
        """Ej: "Día 3/7 — 20 de diciembre — el día del estallido"."""
        etiqueta = CAPITULO_LABEL.get(self.capitulo, "")
        return f"Día {self.capitulo}/{CAPITULOS_TOTALES} — {etiqueta}"

    def generar_estadisticas(self, final_tipo: Optional[str] = None) -> Dict[str, Any]:
        """Resumen de cómo se jugó la partida, para mostrar en la pantalla de
        final (ganado o perdido). Compartido por modo historia y modo libre,
        ver game/engine.py y game/modo_libre.py."""
        hitos = [
            descripcion
            for flag, descripcion in HITOS_DESCRIPCION.items()
            if flag in self.flags
        ]
        dinero_total = (
            self.dinero.pesos + self.dinero.patacones + self.dinero.lecops + self.dinero.creditos_trueque
        )
        puntaje = (
            self.reputacion_barrial
            + self.salud // 2
            + dinero_total // 10
            + self.capitulo * 10
            + len(hitos) * 5
            + len(self.lugares_visitados)
            + FINAL_PUNTAJE_BONUS.get(final_tipo or "", 0)
        )
        return {
            "turnos": self.turno,
            "capitulo": self.capitulo,
            "dia": self.etiqueta_capitulo(),
            "camino": resumen_camino(self.alineacion),
            "alineacion": self.alineacion,
            "reputacion": self.reputacion_barrial,
            "dinero_final": self.dinero.describir(),
            "lugares_recorridos": len(self.lugares_visitados),
            "hitos": hitos,
            "puntaje": puntaje,
        }

    def agregar_item(self, item: str) -> None:
        if item and item not in self.inventario:
            self.inventario.append(item)

    def quitar_item(self, item: str) -> None:
        if item in self.inventario:
            self.inventario.remove(item)

    def tiene_item(self, item: str) -> bool:
        return item in self.inventario

    def tiene_flag(self, flag: str) -> bool:
        return flag in self.flags

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "trasfondo": self.trasfondo,
            "barrio_inicial": self.barrio_inicial,
            "objetivo": self.objetivo,
            "objetivo_categoria": self.objetivo_categoria,
            "zona_gba": self.zona_gba,
            "nodo_actual": self.nodo_actual,
            "ubicacion": self.ubicacion,
            "salud": self.salud,
            "estados": sorted(self.estados),
            "inventario": list(self.inventario),
            "dinero": self.dinero.to_dict(),
            "flags": sorted(self.flags),
            "reputacion_barrial": self.reputacion_barrial,
            "alineacion": self.alineacion,
            "capitulo": self.capitulo,
            "turno": self.turno,
            "vivo": self.vivo,
            "ultima_imagen_url": self.ultima_imagen_url,
            "orden_opciones": list(self.orden_opciones),
            "turno_mision_comedor": self.turno_mision_comedor,
            "lugares_visitados": sorted(self.lugares_visitados),
            "modo": self.modo,
            "escena_libre": self.escena_libre,
            "dialogos_libres": [list(d) for d in self.dialogos_libres],
            "opciones_libres": list(self.opciones_libres),
            "historial_libre": list(self.historial_libre),
            "es_final_libre": self.es_final_libre,
            "final_tipo_libre": self.final_tipo_libre,
        }

    @staticmethod
    def from_dict(datos: Dict[str, Any]) -> "EstadoJugador":
        estado = EstadoJugador(
            nombre=datos["nombre"],
            trasfondo=datos["trasfondo"],
            barrio_inicial=datos["barrio_inicial"],
            objetivo=datos["objetivo"],
            objetivo_categoria=datos.get("objetivo_categoria", "generico"),
        )
        estado.zona_gba = datos.get("zona_gba", "conurbano_generico")
        estado.nodo_actual = datos.get("nodo_actual", "esquina_barrio")
        estado.ubicacion = datos.get("ubicacion", "")
        estado.salud = datos.get("salud", 100)
        estado.estados = set(datos.get("estados", []))
        estado.inventario = list(datos.get("inventario", []))
        estado.dinero = Dinero.from_dict(datos.get("dinero", {}))
        estado.flags = set(datos.get("flags", []))
        estado.reputacion_barrial = datos.get("reputacion_barrial", 0)
        estado.alineacion = datos.get("alineacion", 0)
        estado.capitulo = datos.get("capitulo", 1)
        estado.turno = datos.get("turno", 0)
        estado.vivo = datos.get("vivo", True)
        estado.ultima_imagen_url = datos.get("ultima_imagen_url", "")
        estado.orden_opciones = list(datos.get("orden_opciones", []))
        estado.turno_mision_comedor = datos.get("turno_mision_comedor")
        estado.lugares_visitados = set(datos.get("lugares_visitados", []))
        estado.modo = datos.get("modo", "historia")
        estado.escena_libre = datos.get("escena_libre", "")
        estado.dialogos_libres = [tuple(d) for d in datos.get("dialogos_libres", [])]
        estado.opciones_libres = list(datos.get("opciones_libres", []))
        estado.historial_libre = list(datos.get("historial_libre", []))
        estado.es_final_libre = datos.get("es_final_libre", False)
        estado.final_tipo_libre = datos.get("final_tipo_libre")
        return estado
