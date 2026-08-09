"""App web multijugador (v2) de "2001: Odisea en Buenos Aires".

Mesa chica sin IA: hasta 6 jugadores comparten una sala (Supabase como base
de estado compartido en vez de la cookie de sesión del v1), cada uno juega
su propio personaje sobre el mismo grafo de game/story.py, y todos ven en
vivo lo que hacen los demás (Socket.IO) con un respaldo por polling (REST
liso) para el que no pueda mantener el socket abierto.

No modifica nada de game/, api/, main.py ni templates/static del v1 — los
importa como dependencia de solo lectura.

Correr en local:  python3 v2/app.py
"""

from __future__ import annotations

import os
import sys

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, join_room

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import salas  # noqa: E402
from game import engine  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-v2-cambiar-en-produccion")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def _emitir_actualizacion(sala_id: str, evento_extra: dict | None = None) -> None:
    sala = salas.obtener_sala(sala_id)
    jugadores = salas.listar_jugadores(sala_id)
    payload = {"sala": sala, "jugadores": jugadores}
    if evento_extra:
        payload["evento"] = evento_extra
    socketio.emit("actualizacion", payload, to=sala_id)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/salas", methods=["POST"])
def api_crear_sala():
    body = request.get_json(silent=True) or {}
    modo = str(body.get("modo", "historia"))
    sala = salas.crear_sala(modo)
    return jsonify({"sala": sala})


@app.route("/api/salas/<codigo>", methods=["GET"])
def api_obtener_sala(codigo):
    sala = salas.obtener_sala_por_codigo(codigo)
    if sala is None:
        return jsonify({"error": "No existe ninguna sala con ese código."}), 404
    jugadores = salas.listar_jugadores(sala["id"])
    return jsonify({"sala": sala, "jugadores": jugadores})


@app.route("/api/salas/<codigo>/eventos", methods=["GET"])
def api_eventos(codigo):
    sala = salas.obtener_sala_por_codigo(codigo)
    if sala is None:
        return jsonify({"error": "No existe ninguna sala con ese código."}), 404
    desde = request.args.get("desde", "0")
    try:
        desde_id = int(desde)
    except ValueError:
        desde_id = 0
    return jsonify({"eventos": salas.listar_eventos_desde(sala["id"], desde_id)})


@app.route("/api/salas/<codigo>/unirse", methods=["POST"])
def api_unirse(codigo):
    body = request.get_json(silent=True) or {}
    nombre = str(body.get("nombre", "")).strip()[:80]
    trasfondo = str(body.get("trasfondo", ""))[:200]
    barrio = str(body.get("barrio", ""))[:120]
    objetivo = str(body.get("objetivo", ""))[:200]
    if not nombre or not trasfondo or not barrio or not objetivo:
        return jsonify({"error": "Completá los cuatro datos para sumarte a la mesa."}), 400
    try:
        sala, jugador = salas.unirse_a_sala(codigo, nombre, trasfondo, barrio, objetivo)
    except salas.ErrorSala as err:
        return jsonify({"error": str(err)}), 400
    _emitir_actualizacion(sala["id"], {"tipo": "union", "mensaje": f"{nombre} se sumó a la mesa."})
    return jsonify({"sala": sala, "jugador": jugador})


@app.route("/api/jugadores/<jugador_id>", methods=["GET"])
def api_jugador_vista(jugador_id):
    jugador_row = salas.obtener_jugador(jugador_id)
    if jugador_row is None:
        return jsonify({"error": "No se encontró ese jugador."}), 404
    estado = salas.cargar_estado_jugador(jugador_row)
    vista = engine.vista_actual(estado)
    vista = salas.anotar_vista_con_mundo(jugador_row["sala_id"], vista)
    sala = salas.obtener_sala(jugador_row["sala_id"])
    return jsonify({"vista": vista, "jugador": jugador_row, "sala": sala})


@app.route("/api/jugadores/<jugador_id>/accion", methods=["POST"])
def api_jugador_accion(jugador_id):
    jugador_row = salas.obtener_jugador(jugador_id)
    if jugador_row is None:
        return jsonify({"error": "No se encontró ese jugador."}), 404

    body = request.get_json(silent=True) or {}
    tipo = body.get("tipo")
    valor = body.get("valor", "")
    try:
        if tipo == "opcion":
            vista = salas.jugar_opcion(jugador_id, int(valor))
        elif tipo == "libre":
            vista = salas.jugar_accion_libre(jugador_id, str(valor))
        else:
            return jsonify({"error": "Tipo de acción inválido."}), 400
    except salas.ErrorSala as err:
        return jsonify({"error": str(err)}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Opción inválida."}), 400

    sala_id = jugador_row["sala_id"]
    jugador_actualizado = salas.obtener_jugador(jugador_id)
    _emitir_actualizacion(
        sala_id,
        {"tipo": "accion", "mensaje": f"{jugador_actualizado['nombre']} jugó su turno."},
    )
    return jsonify({"vista": vista})


@socketio.on("unirse_sala")
def socket_unirse_sala(data):
    sala_id = (data or {}).get("sala_id")
    if sala_id:
        join_room(sala_id)


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5100))
    socketio.run(app, host="0.0.0.0", port=puerto, debug=True, allow_unsafe_werkzeug=True)
