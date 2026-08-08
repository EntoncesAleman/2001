#!/usr/bin/env python3
"""Argentina 2001 — RPG textual de supervivencia. Frontend de terminal.

Ejecutar con:  python3 main.py
Ver README.md para instalar dependencias y para la variante web (Flask/Vercel).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

from game import engine
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
                "ARGENTINA 2001\nSupervivencia en el Gran Buenos Aires",
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
        "[dim](copiá y pegá el link en el navegador para ver la ilustración pixel art)[/dim]"
    )
    console.print(Rule(style="yellow"))
    console.print()


def mostrar_narracion(narracion: str) -> None:
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
            "huida": "🚌 FIN — TE FUISTE DEL GRAN BUENOS AIRES",
            "solitario": "🚪 FIN — SOBREVIVISTE, SOLO",
        }
        etiqueta = etiquetas.get(vista.get("final_tipo"), "FIN DE LA PARTIDA")
        console.print(Panel(etiqueta, border_style="bold red", padding=(1, 2)))
    else:
        mostrar_opciones(vista["opciones"])


# ---------------------------------------------------------------------------
# Alta de personaje (paso inicial)
# ---------------------------------------------------------------------------

def alta_de_personaje() -> EstadoJugador:
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
    estado = engine.crear_estado(nombre, trasfondo, barrio, objetivo)
    return estado


# ---------------------------------------------------------------------------
# Guardado / carga
# ---------------------------------------------------------------------------

def guardar_partida(estado: EstadoJugador, archivo: str = ARCHIVO_PARTIDA_DEFAULT) -> None:
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(engine.guardar_estado(estado), f, ensure_ascii=False, indent=2)
    console.print(f"[green]Partida guardada en {archivo}[/green]\n")


def cargar_partida(archivo: str = ARCHIVO_PARTIDA_DEFAULT) -> Optional[EstadoJugador]:
    if not os.path.isfile(archivo):
        return None
    with open(archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return engine.cargar_estado(datos)


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
        nodo_opciones = len(engine.vista_actual(estado)["opciones"])
        if 1 <= numero <= nodo_opciones:
            return engine.elegir_opcion(estado, numero)
        return {
            "mensaje_error": (
                "Ese número no corresponde a ninguna opción de la lista. "
                "Elegí uno de los listados o escribí directamente tu acción."
            )
        }
    return engine.accion_libre(estado, entrada)


def loop_juego(estado: EstadoJugador) -> None:
    vista = engine.vista_actual(estado)
    mostrar_vista(vista)

    while True:
        if vista["es_final"]:
            console.print("\n[bold]¿Querés jugar otra partida? (si/no)[/bold]")
            de_nuevo = Prompt.ask("", choices=["si", "no"], default="no")
            if de_nuevo == "si":
                estado = alta_de_personaje()
                vista = engine.vista_actual(estado)
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
            vista = engine.accion_libre(estado, texto_libre)
            console.print()
            mostrar_vista(vista)
            continue

        vista = procesar_turno(estado, entrada)
        if vista.get("mensaje_error"):
            console.print(f"[red]{vista['mensaje_error']}[/red]\n")
            vista = engine.vista_actual(estado)
            continue

        console.print()
        mostrar_vista(vista)


def main() -> None:
    mostrar_titulo()

    estado = preguntar_continuar_partida_guardada()
    if estado is None:
        estado = alta_de_personaje()

    try:
        loop_juego(estado)
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[bold cyan]Partida interrumpida. ¡Cuidate!\n[/bold cyan]")
        sys.exit(0)


if __name__ == "__main__":
    main()
