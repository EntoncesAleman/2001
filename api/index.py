"""App web (Flask) de "Argentina 2001".

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

from flask import Flask, jsonify, render_template, request, session

# Permite ejecutar tanto como módulo (`vercel`, que importa `api.index`) como
# script suelto (`python3 api/index.py`) sin duplicar el paquete `game`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import engine  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-cambiar-en-produccion-2001")


def _vista_desde_sesion():
    datos_estado = session.get("estado")
    if not datos_estado:
        return None, None
    estado = engine.cargar_estado(datos_estado)
    return estado, engine.vista_actual(estado)


def _guardar_estado_en_sesion(estado) -> None:
    session["estado"] = engine.guardar_estado(estado)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/estado", methods=["GET"])
def api_estado():
    estado, vista = _vista_desde_sesion()
    if estado is None:
        return jsonify({"activo": False})
    return jsonify({"activo": True, "vista": vista})


@app.route("/api/nueva_partida", methods=["POST"])
def api_nueva_partida():
    body = request.get_json(silent=True) or {}
    nombre = str(body.get("nombre", ""))[:80]
    trasfondo = str(body.get("trasfondo", ""))[:200]
    barrio = str(body.get("barrio", ""))[:120]
    objetivo = str(body.get("objetivo", ""))[:200]

    if not nombre.strip() or not trasfondo.strip() or not barrio.strip() or not objetivo.strip():
        return jsonify({"error": "Completá los cuatro datos para arrancar la partida."}), 400

    estado = engine.crear_estado(nombre, trasfondo, barrio, objetivo)
    _guardar_estado_en_sesion(estado)
    return jsonify({"vista": engine.vista_actual(estado)})


@app.route("/api/accion", methods=["POST"])
def api_accion():
    estado, _ = _vista_desde_sesion()
    if estado is None:
        return jsonify({"error": "No hay una partida en curso. Empezá una nueva."}), 400

    body = request.get_json(silent=True) or {}
    tipo = body.get("tipo")
    valor = body.get("valor", "")

    if tipo == "opcion":
        try:
            indice = int(valor)
        except (TypeError, ValueError):
            return jsonify({"error": "Opción inválida."}), 400
        vista = engine.elegir_opcion(estado, indice)
    elif tipo == "libre":
        vista = engine.accion_libre(estado, str(valor))
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
