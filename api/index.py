"""App web (Flask) de "2001: Odisea en Buenos Aires".

Reutiliza exactamente el mismo `game/engine.py` que usa `main.py` (CLI): acá
solo se traduce esa API a rutas HTTP con estado guardado en la cookie de
sesión firmada de Flask (no hace falta base de datos, lo cual la hace apta
para desplegarse en Vercel como función serverless sin estado persistente
entre invocaciones).

Correr en local:   python3 api/index.py
Desplegar:         vercel deploy   (ver vercel.json y README.md)
"""

from __future__ import annotations

import os
import sys
from typing import Any

from flask import Flask, jsonify, render_template, request, session

# Permite ejecutar tanto como módulo (`vercel`, que importa `api.index`) como
# script suelto (`python3 api/index.py`) sin duplicar el paquete `game`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import engine, images, llm, modo_libre  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-cambiar-en-produccion-2001")


# El estado guardado en sesión trae su propio campo "modo" ("historia" o
# "libre"): estas funciones son el único lugar que necesita saber a cuál de
# los dos motores (game/engine.py o game/modo_libre.py) hay que llamar.
def _motor_de(estado) -> Any:
    return modo_libre if estado.modo == "libre" else engine


def _vista_desde_sesion():
    datos_estado = session.get("estado")
    if not datos_estado:
        return None, None
    modo = datos_estado.get("modo", "historia")
    motor = modo_libre if modo == "libre" else engine
    estado = motor.cargar_estado(datos_estado)
    vista = motor.vista_actual_libre(estado) if modo == "libre" else motor.vista_actual(estado)
    return estado, vista


def _guardar_estado_en_sesion(estado) -> None:
    motor = _motor_de(estado)
    session["estado"] = motor.guardar_estado(estado)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/modo_disponible")
def api_modo_disponible():
    return jsonify({"libre_disponible": llm.modelo_configurado()})


# Fotogramas fijos de la cutscene de apertura: dos imágenes estáticas con
# paneo/zoom de cámara (estilo intro de recreativo) — la calle en caos frente
# a la Casa Rosada, corte directo al helicóptero presidencial alejándose.
# Usan el mismo estilo visual (`images.build_pollinations_url`) que el resto
# del juego, con seeds fijas para que la escena no cambie en cada carga.
#
# Nota: el modelo de Pollinations no logra combinar "helicóptero" + "Casa
# Rosada" en una sola imagen de forma confiable (probado con varias
# variantes: o sale el palacio sin helicóptero, o el helicóptero sin
# palacio) — separarlos en dos tomas y dejar que el corte narrativo conecte
# ambas (como en cualquier edición de cine) da mejor resultado que forzarlos
# juntos.
@app.route("/api/intro")
def api_intro():
    # Nota: "Casa Rosada" como nombre propio no lo reconoce bien el modelo de
    # Pollinations (devuelve escenas genéricas sin relación); describirla
    # visualmente ("pink colonial government palace with a central dome") da
    # resultados mucho más fieles.
    return jsonify({
        "calle": images.build_pollinations_url(
            "a huge angry crowd clashing with police at night in a plaza in front of a "
            "pink colonial government palace with a central dome, burning barricades, "
            "thick smoke, cacerolazo protesters banging pots, dramatic wide establishing "
            "shot",
            ancho=960, alto=540, seed=555,
        ),
        "helicoptero": images.build_pollinations_url(
            "a realistic military utility helicopter, the same general shape as a Bell "
            "UH-1 Iroquois, with visible spinning rotor blades flying away at dusk, NOT "
            "futuristic, NOT a spaceship, ordinary real-world aircraft, large and "
            "prominent in frame, the city below covered in smoke with an orange fire glow "
            "on the horizon",
            ancho=960, alto=540, seed=321,
        ),
    })


@app.route("/api/estado", methods=["GET"])
def api_estado():
    estado, vista = _vista_desde_sesion()
    if estado is None:
        return jsonify({"activo": False})
    return jsonify({"activo": True, "vista": vista})


@app.route("/api/nueva_partida", methods=["POST"])
def api_nueva_partida():
    body = request.get_json(silent=True) or {}
    modo = str(body.get("modo", "historia")).strip().lower()
    nombre = str(body.get("nombre", ""))[:80]
    trasfondo = str(body.get("trasfondo", ""))[:200]
    barrio = str(body.get("barrio", ""))[:120]
    objetivo = str(body.get("objetivo", ""))[:200]

    if not nombre.strip() or not trasfondo.strip() or not barrio.strip() or not objetivo.strip():
        return jsonify({"error": "Completá los cuatro datos para arrancar la partida."}), 400

    if modo == "libre":
        estado = modo_libre.iniciar_partida_libre(nombre, trasfondo, barrio, objetivo)
        if estado is None:
            return jsonify({
                "error": (
                    "El modo libre necesita una API key de Gemini o Anthropic configurada "
                    "en el servidor y no encontré ninguna (o falló la primera llamada). "
                    "Probá el modo historia mientras tanto."
                )
            }), 400
        _guardar_estado_en_sesion(estado)
        return jsonify({"vista": modo_libre.vista_actual_libre(estado)})

    estado = engine.crear_estado(nombre, trasfondo, barrio, objetivo)
    _guardar_estado_en_sesion(estado)
    return jsonify({"vista": engine.vista_actual(estado)})


@app.route("/api/accion", methods=["POST"])
def api_accion():
    estado, _ = _vista_desde_sesion()
    if estado is None:
        return jsonify({"error": "No hay una partida en curso. Empezá una nueva."}), 400

    motor = _motor_de(estado)
    body = request.get_json(silent=True) or {}
    tipo = body.get("tipo")
    valor = body.get("valor", "")

    if tipo == "opcion":
        try:
            indice = int(valor)
        except (TypeError, ValueError):
            return jsonify({"error": "Opción inválida."}), 400
        vista = motor.elegir_opcion_libre(estado, indice) if estado.modo == "libre" else motor.elegir_opcion(estado, indice)
    elif tipo == "libre":
        vista = motor.accion_libre_libre(estado, str(valor)) if estado.modo == "libre" else motor.accion_libre(estado, str(valor))
    else:
        return jsonify({"error": "Tipo de acción inválido."}), 400

    _guardar_estado_en_sesion(estado)
    return jsonify({"vista": vista})


@app.route("/api/reiniciar", methods=["POST"])
def api_reiniciar():
    session.pop("estado", None)
    return jsonify({"ok": True})


# Punto de entrada para correr localmente con `python3 api/index.py`.
# En Vercel, la plataforma importa directamente el objeto `app` de este
# módulo (ver vercel.json) y nunca ejecuta este bloque.
if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=True)
