# v2 — Mesa multijugador (experimental)

Versión aparte del juego original (que sigue en la raíz del repo, sin
tocar). Mesa chica sin IA: hasta 6 jugadores comparten una sala, cada uno
juega su propio personaje sobre el mismo grafo de nodos de `game/story.py`
(reutilizado tal cual), y todos ven en vivo lo que hacen los demás.

## Cómo correrlo en local

```bash
python3 -m venv .venv   # o reusar el .venv de la raíz del repo
source .venv/bin/activate
pip install -r v2/requirements.txt
python3 v2/app.py       # sirve en http://localhost:5100
```

Necesita las variables de entorno `SUPABASE_URL` y `SUPABASE_KEY` (la key
"anon"/pública). Si no se setean, usa por defecto el proyecto Supabase
`odisea-2001-multijugador` creado para este prototipo — andá a
[supabase.com/dashboard](https://supabase.com/dashboard) con la cuenta
correspondiente para ver/administrar los datos, o crear tu propio proyecto
y correr el SQL de `esquema.sql` (ver abajo) en uno nuevo.

## Arquitectura

- **Supabase (Postgres)** reemplaza la cookie de sesión del v1 como fuente
  de verdad del estado — así todos los jugadores de una sala ven el mismo
  mundo. Tablas: `salas` (lobby/estado de la partida), `jugadores` (un
  `EstadoJugador` completo por fila, serializado en la columna
  `estado_json`, más algunas columnas sueltas livianas para poder
  ordenar/filtrar sin deserializar), `mundo_flags` (estado compartido:
  ej. si alguien ya resolvió el saqueo del supermercado) y `eventos` (feed
  de actividad de la sala).
- **Flask + Flask-SocketIO**: las acciones de juego son rutas REST
  normales (`POST /api/jugadores/<id>/accion`); cada acción, además,
  dispara un `emit` de Socket.IO a la sala para que los demás se enteren
  en el momento. El frontend además hace polling REST cada 4s de forma
  independiente (no solo como respaldo si el socket se cae: los dos
  caminos corren en paralelo).
- **RLS permisivo**: es un juego casual sin login ni datos sensibles más
  allá de un nombre elegido por el jugador, así que las políticas de Row
  Level Security son `using (true)` — cualquiera con el código de sala
  puede leer/escribir. El backend de Flask es quien en la práctica valida
  las reglas del juego antes de tocar la base.

## Reglas de la mesa

- Mínimo 3 jugadores para arrancar (automático, sin botón), máximo 6.
- No se puede sumar gente una vez que la partida ya está `en_curso`.
- Presupuesto de turnos COMPARTIDO por toda la mesa (columna
  `salas.limite_turnos`, 300 por defecto): se suma 1 cada vez que
  cualquier jugador hace una acción. "Se acaban los días" cuando se agota
  ese pozo compartido, o antes si todos los jugadores ya llegaron a su
  final personal.
- Al cerrarse la partida: si NINGÚN jugador llegó al final
  `objetivo_cumplido` (completó su misión personal — retirar los ahorros,
  encontrar al familiar, salvar el negocio, según lo que haya elegido en
  "elegir_mision"), la mesa entera pierde (`derrota_colectiva`). Si al
  menos uno lo logró, gana quien tenga el puntaje más alto
  (`game/state.py:generar_estadisticas`), sin importar si los demás
  también cumplieron su objetivo o no.

  **Nota de diseño a revisar**: llegar a un final "lindo" pero que no sea
  específicamente `objetivo_cumplido` (por ejemplo `comunidad`, el mejor
  final del camino legal en el v1) NO cuenta como "completar la misión" en
  este criterio estricto — solo cuenta la misión personal elegida al
  principio. Si se prefiere que cualquier final positivo cuente, hay que
  ajustar `salas.py:verificar_fin_de_partida`.

## Qué falta (no incluido en este primer corte)

- **Modo con IA** (gente que entra y sale en cualquier momento, hasta 6
  jugadores, narrador compartido vía LLM): esta v2 solo cubre la "mesa
  chica sin IA" pedida como primer paso. Se apoyaría en la misma base
  (`salas`/`jugadores`/`eventos`) sumando un narrador que reemplace las
  respuestas de `game/story.py` por las de `game/llm.py` en modo libre,
  compartido entre todos los que estén conectados en ese momento.
- **Efectos mecánicos de "mundo compartido"** más allá del saqueo del
  supermercado: hoy solo ese caso está enganchado (ver
  `salas._mundo_anotar_saqueo_si_corresponde`); es un patrón fácil de
  repetir para otros nodos si se quiere que más lugares "recuerden" lo que
  hizo otro jugador de la mesa.
- **Optimización de latencia**: cada acción de un jugador dispara varias
  llamadas a Supabase en secuencia (cargar jugador, cargar sala, guardar
  jugador, actualizar turno global, chequear fin de partida). Medido en
  este entorno de desarrollo, son ~1-1.5s por turno — jugable, pero se
  podría bajar agrupando algunas de esas llamadas en una única función
  RPC de Postgres si hiciera falta más velocidad.
