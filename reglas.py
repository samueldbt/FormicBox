"""Tabla de prioridades de comportamiento (editable por el equipo).

Cada obrera evalúa estas reglas EN ORDEN y se queda con la primera que se cumple
(esa regla fija el estado y termina la evaluación). Para cambiar prioridades basta
con reordenar la tupla. La última siempre debe ser "EXPLORE".

Reglas (cada una es un método `_rule_<nombre>` en Hormigas/worker.py):
  FLEE         huir del fuego visible o de la feromona de alarma
  REFUEL_NEST  en el nido: entregar carga o botín, comer hasta llenarse y salir a explorar
  EAT_MAP      comer un bocadillo del mapa si tiene hambre
  LOOT         recoger el botín de una marabunta caída y llevarlo al nido
  PICKUP       tomar el recurso de la celda en la que está
  GO_FEED      volver al nido a comer si la energía no alcanza para el regreso y hay reservas
  SEARCH       fuente agotada: búsqueda local en espiral antes de rendirse
  CLEAN        retroceder borrando un rastro muerto (opcional, CLEAN_DEAD_TRAILS)
  EXPLORE      explorar (seguir rastro, ir al recurso visto/recordado)
"""

WORKER_RULES = ("FLEE", "REFUEL_NEST", "EAT_MAP", "LOOT", "PICKUP", "GO_FEED", "SEARCH", "CLEAN", "EXPLORE")