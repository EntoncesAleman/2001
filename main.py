#!/usr/bin/env python3
"""2001: Odisea en Buenos Aires — RPG textual de supervivencia. Frontend de terminal.

Ejecutar con:  python3 main.py
Ver README.md para instalar dependencias y para la variante web (Flask/Vercel).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

from game import engine, llm, modo_libre
from game.state import EstadoJugador

console = Console()

CARPETA_PARTIDAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "partidas")
ARCHIVO_PARTIDA_DEFAULT = os.path.join(CARPETA_PARTIDAS, "partida.json")


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def mostrar_titulo() -> None:
    console.print()
    console.print(
        Panel(
            Text(
                "2001: ODISEA EN BUENOS AIRES\nSupervivencia en el Gran Buenos Aires",
                justify="center",
                style="bold white on dark_blue",
            ),
            border_style="dark_blue",
            padding=(1, 4),
        )
    )
    console.print(
        "[dim]Diciembre de 2001. El Corralito, los Patacones, las asambleas, los cacerolazos.[/dim]",
        justify="center",
    )
    console.print()


def mostrar_imagen(url: Optional[str]) -> None:
    if not url:
        return
    console.print()
    console.print(Rule("[bold yellow]ESCENA CLAVE[/bold yellow]", style="yellow"))
    console.print(f"[yellow]🖼  {url}[/yellow]")
    console.print(
        "[dim](copiá y pegá el link en el navegador para ver la ilustración de la escena)[/dim]"
    )
    console.print(Rule(style="yellow"))
    console.print()


VELOCIDAD_TIPEO_SEGUNDOS = 0.012


def mostrar_narracion(narracion: str) -> None:
    # Efecto "máquina de escribir" (tipo Carmen Sandiego): si la salida no es
    # una terminal real (pipe, redirección, tests) tipear caracter por
    # caracter no tiene sentido, así que ahí se imprime todo de una.
    if console.is_terminal:
        for caracter in narracion:
            console.print(caracter, style="white", end="")
            time.sleep(VELOCIDAD_TIPEO_SEGUNDOS)
        console.print()
    else:
        console.print(narracion, style="white")
    console.print()


def mostrar_dialogos(dialogos) -> None:
    for personaje, texto in dialogos:
        console.print(f'[bold yellow]{personaje}:[/bold yellow] "[italic]{texto}[/italic]"')
    if dialogos:
        console.print()


def mostrar_panel_estado(vista: dict) -> None:
    panel = vista["panel"]
    linea = "-" * 50
    cuerpo = (
        f"{linea}\n"
        f"🗓️  {panel.get('dia', '')}\n"
        f"🎯 Misión: {panel.get('mision', '')}\n"
        f"📍 Ubicación: {panel['ubicacion']}\n"
        f"🎒 Inventario/Recursos: {panel['inventario']}\n"
        f"⚠️  Estado/Salud: {panel['salud']}\n"
        f"{linea}"
    )
    console.print(cuerpo, style="bold cyan")
    console.print()


def mostrar_opciones(opciones) -> None:
    console.print("[bold green]Opciones Tácticas:[/bold green]")
    for i, texto in enumerate(opciones, start=1):
        console.print(f"  [bold green][{i}][/bold green] {texto}")
    console.print(
        f"  [bold green][{len(opciones) + 1}][/bold green] [dim](Escribí tu propia acción libre)[/dim]"
    )
    console.print()


def mostrar_vista(vista: dict) -> None:
    mostrar_imagen(vista.get("imagen_url"))
    mostrar_narracion(vista["narracion"])
    mostrar_dialogos(vista["dialogos"])
    if vista.get("mensaje_efecto"):
        console.print(f"[italic magenta]{vista['mensaje_efecto']}[/italic magenta]")
        console.print()
    if vista.get("mensaje_libre"):
        console.print(vista["mensaje_libre"], style="white")
        console.print()
    mostrar_panel_estado(vista)
    if vista["es_final"]:
        etiquetas = {
            "muerte": "☠️  FIN — NO SOBREVIVISTE",
            "objetivo_cumplido": "🏁 FIN — CUMPLISTE TU OBJETIVO",
            "comunidad": "🤝 FIN — SALISTE ADELANTE CON EL BARRIO",
            "solitario": "🚪 FIN — SOBREVIVISTE, SOLO",
            "condenado": "🚔 FIN — TE DICTARON LA PRISIÓN PREVENTIVA",
            "represion_derrota": "🪧 FIN — REPRIMIERON EL PIQUETE",
            "muerte_manifestacion": "🚑 FIN — NO SOBREVIVISTE (te agarró en la calle)",
            "cartonero": "🛒 FIN — TERMINASTE DE CARTONERO",
            "referente_piquetero": "✊ FIN — TE CONVERTISTE EN REFERENTE PIQUETERO",
            "presidente": "🎖️  FIN — TERMINASTE SIENDO PRESIDENTE",
            "perdido": "💊 FIN — TE PERDISTE EN EL CONSUMO",
        }
        etiqueta = etiquetas.get(vista.get("final_tipo"), "FIN DE LA PARTIDA")
        console.print(Panel(etiqueta, border_style="bold red", padding=(1, 2)))
        mostrar_estadisticas(vista.get("estadisticas"))
    else:
        mostrar_opciones(vista["opciones"])


def mostrar_estadisticas(stats: dict | None) -> None:
    if not stats:
        return
    lineas = [
        f"🏆 Puntaje final: {stats['puntaje']}",
        f"🗓️  Llegaste a: {stats['dia']}",
        f"🧭 Camino recorrido: {stats['camino']} (alineación {stats['alineacion']:+d})",
        f"🤝 Reputación barrial final: {stats['reputacion']}",
        f"💰 Terminaste con: {stats['dinero_final']}",
        f"🚶 Lugares distintos recorridos: {stats['lugares_recorridos']}",
        f"⏱️  Turnos jugados: {stats['turnos']}",
    ]
    if stats["hitos"]:
        lineas.append("")
        lineas.append("Hitos de esta partida:")
        lineas.extend(f"  • {hito}" for hito in stats["hitos"])
    console.print(Panel("\n".join(lineas), title="Estadísticas de la partida", border_style="cyan", padding=(1, 2)))


# ---------------------------------------------------------------------------
# Motor: en modo "historia" es game/engine.py, en modo "libre" es
# game/modo_libre.py. Estas funciones son el único lugar de main.py que
# necesita saber cuál de los dos corresponde.
# ---------------------------------------------------------------------------

def _motor_de(estado: EstadoJugador):
    return modo_libre if estado.modo == "libre" else engine


def vista_actual_de(estado: EstadoJugador) -> dict:
    motor = _motor_de(estado)
    return motor.vista_actual_libre(estado) if estado.modo == "libre" else motor.vista_actual(estado)


def elegir_opcion_de(estado: EstadoJugador, indice: int) -> dict:
    motor = _motor_de(estado)
    return motor.elegir_opcion_libre(estado, indice) if estado.modo == "libre" else motor.elegir_opcion(estado, indice)


def accion_libre_de(estado: EstadoJugador, texto: str) -> dict:
    motor = _motor_de(estado)
    return motor.accion_libre_libre(estado, texto) if estado.modo == "libre" else motor.accion_libre(estado, texto)


# ---------------------------------------------------------------------------
# Selección de modo + alta de personaje (paso inicial)
# ---------------------------------------------------------------------------

def elegir_modo() -> str:
    libre_disponible = llm.modelo_configurado()
    console.print(
        Panel(
            "[bold]MODO HISTORIA[/bold] — ramificaciones ya escritas, la misma para todos, "
            "funciona sin ninguna IA.\n"
            "[bold]MODO LIBRE (IA)[/bold] — improvisado turno a turno por un modelo de IA, "
            "nunca se repite igual."
            + ("" if libre_disponible else "\n[dim](no disponible: no hay API key configurada)[/dim]"),
            title="¿Cómo querés jugar?",
            border_style="blue",
        )
    )
    if not libre_disponible:
        return "historia"
    return Prompt.ask("Elegí un modo", choices=["historia", "libre"], default="historia")


def alta_de_personaje(modo: str = "historia") -> EstadoJugador:
    console.print(
        "Antes de arrancar necesito algunos datos tuyos. En cualquier pregunta podés "
        "escribir lo que quieras, no hace falta que sea una de las sugerencias.\n",
        style="white",
    )

    nombre = Prompt.ask("[bold]¿Cómo te llamás?[/bold]")

    console.print(
        "\n[dim]Ejemplos de trasfondo: empleado bancario, estudiante universitario, "
        "comerciante, chofer de colectivo, militante barrial...[/dim]"
    )
    trasfondo = Prompt.ask("[bold]¿Cuál es tu trasfondo?[/bold]")

    console.print(
        "\n[dim]Ejemplos: un barrio del Conurbano Norte/Sur/Oeste, o algún barrio de CABA...[/dim]"
    )
    barrio = Prompt.ask("[bold]¿De qué barrio salís?[/bold]")

    console.print(
        "\n[dim]Ejemplos: salvar el negocio familiar, llegar al centro a retirar tus ahorros, "
        "buscar a un familiar perdido en un saqueo, escapar de la represión...[/dim]"
    )
    objetivo = Prompt.ask("[bold]¿Cuál es tu objetivo principal?[/bold]")

    console.print()

    if modo == "libre":
        estado = modo_libre.iniciar_partida_libre(nombre, trasfondo, barrio, objetivo)
        if estado is None:
            console.print(
                "[red]No se pudo arrancar el modo libre (sin API key configurada, o falló la "
                "primera llamada). Arrancamos en modo historia.[/red]\n"
            )
            estado = engine.crear_estado(nombre, trasfondo, barrio, objetivo)
        return estado

    return engine.crear_estado(nombre, trasfondo, barrio, objetivo)


# ---------------------------------------------------------------------------
# Guardado / carga
# ---------------------------------------------------------------------------

def guardar_partida(estado: EstadoJugador, archivo: str = ARCHIVO_PARTIDA_DEFAULT) -> None:
    # to_dict/from_dict son iguales en los dos motores (incluyen los campos
    # de ambos modos), así que guardar/cargar no necesita saber qué modo es.
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(estado.to_dict(), f, ensure_ascii=False, indent=2)
    console.print(f"[green]Partida guardada en {archivo}[/green]\n")


def cargar_partida(archivo: str = ARCHIVO_PARTIDA_DEFAULT) -> Optional[EstadoJugador]:
    if not os.path.isfile(archivo):
        return None
    with open(archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return EstadoJugador.from_dict(datos)


def preguntar_continuar_partida_guardada() -> Optional[EstadoJugador]:
    if not os.path.isfile(ARCHIVO_PARTIDA_DEFAULT):
        return None
    respuesta = Prompt.ask(
        "Encontré una partida guardada. ¿Querés continuarla?",
        choices=["si", "no"],
        default="si",
    )
    if respuesta == "si":
        try:
            return cargar_partida()
        except (json.JSONDecodeError, KeyError, OSError):
            console.print("[red]No pude leer la partida guardada, arranco una nueva.[/red]\n")
            return None
    return None


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

AYUDA = (
    "[dim]Comandos especiales en cualquier momento: 'guardar' para guardar la partida, "
    "'salir' para terminar el juego.[/dim]"
)


def pedir_accion(cantidad_opciones: int) -> str:
    console.print(AYUDA)
    return Prompt.ask("\n[bold]¿Qué hacés?[/bold]").strip()


def procesar_turno(estado: EstadoJugador, entrada: str) -> dict:
    if entrada.isdigit():
        numero = int(entrada)
        nodo_opciones = len(vista_actual_de(estado)["opciones"])
        if 1 <= numero <= nodo_opciones:
            return elegir_opcion_de(estado, numero)
        return {
            "mensaje_error": (
                "Ese número no corresponde a ninguna opción de la lista. "
                "Elegí uno de los listados o escribí directamente tu acción."
            )
        }
    return accion_libre_de(estado, entrada)


def loop_juego(estado: EstadoJugador) -> None:
    vista = vista_actual_de(estado)
    mostrar_vista(vista)

    while True:
        if vista["es_final"]:
            console.print("\n[bold]¿Querés jugar otra partida? (si/no)[/bold]")
            de_nuevo = Prompt.ask("", choices=["si", "no"], default="no")
            if de_nuevo == "si":
                modo = elegir_modo()
                estado = alta_de_personaje(modo)
                vista = vista_actual_de(estado)
                mostrar_vista(vista)
                continue
            console.print("\n[bold cyan]Gracias por jugar. Suerte ahí afuera, che.[/bold cyan]\n")
            return

        entrada = pedir_accion(len(vista["opciones"]))

        if entrada.lower() in ("salir", "salir()", "exit", "quit"):
            guardar = Prompt.ask("¿Guardar la partida antes de salir?", choices=["si", "no"], default="si")
            if guardar == "si":
                guardar_partida(estado)
            console.print("\n[bold cyan]Nos vemos, che. Cuidate ahí afuera.[/bold cyan]\n")
            return

        if entrada.lower() in ("guardar",):
            guardar_partida(estado)
            continue

        if not entrada:
            console.print("[red]Escribí un número de opción o una acción.[/red]\n")
            continue

        # El último número de la lista ("[N+1] Escribí tu propia acción libre")
        # es solo una pista visual: si el jugador lo tipea literalmente, hay
        # que pedirle el texto real en vez de mandar el numeral como acción.
        if entrada.isdigit() and int(entrada) == len(vista["opciones"]) + 1:
            texto_libre = Prompt.ask("[bold]Escribí tu acción[/bold]").strip()
            if not texto_libre:
                console.print("[red]No escribiste nada.[/red]\n")
                continue
            vista = accion_libre_de(estado, texto_libre)
            console.print()
            mostrar_vista(vista)
            continue

        vista = procesar_turno(estado, entrada)
        if vista.get("mensaje_error"):
            console.print(f"[red]{vista['mensaje_error']}[/red]\n")
            vista = vista_actual_de(estado)
            continue

        console.print()
        mostrar_vista(vista)


def main() -> None:
    mostrar_titulo()

    estado = preguntar_continuar_partida_guardada()
    if estado is None:
        modo = elegir_modo()
        estado = alta_de_personaje(modo)

    try:
        loop_juego(estado)
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[bold cyan]Partida interrumpida. ¡Cuidate!\n[/bold cyan]")
        sys.exit(0)


if __name__ == "__main__":
    main()
