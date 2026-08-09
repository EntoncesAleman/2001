"""Cliente de Supabase para el v2 multijugador.

Usa la key "anon" porque las tablas tienen RLS permisivo (ver la migración
"esquema_inicial_multijugador" del proyecto odisea-2001-multijugador): es un
juego casual sin login ni datos sensibles más allá de un nombre elegido por
el jugador, así que no hace falta la service_role key. Si el día de mañana
se agrega autenticación real, esto es lo primero que hay que endurecer
(políticas RLS por dueño de fila, no "true" a secas).
"""

from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://aruflxxsyysmlznqymrk.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFydWZseHhzeXlzbWx6bnF5bXJrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyODI0MjIsImV4cCI6MjEwMTg1ODQyMn0.NibXp0qpTke7hjfyNHAXCBDyFmnhL3WaATOJh_W5M6Y",
)


@lru_cache(maxsize=1)
def obtener_cliente() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
