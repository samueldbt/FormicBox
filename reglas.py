"""Tabla de prioridades de comportamiento (editable por el equipo).

Cada obrera evalúa estas reglas EN ORDEN y se queda con la primera que se cumple
(esa regla fija el estado y termina la evaluación). Para cambiar prioridades basta
con reordenar la tupla. La última siempre debe ser "EXPLORE".

Reglas (cada una es un método `_rule_<nombre>` en Hormigas/worker.py):
  FLEE         huir del fuego visible o de la feromona de alarma
  REFUEL_NEST  en el nido: entregar carga, comer hasta llenarse y salir a explorar
  EAT_MAP      comer un bocadillo del mapa si tiene hambre
  PICKUP       tomar el recurso de la celda en la que está
  GO_FEED      volver al nido a comer si la energía no alcanza para el regreso y hay reservas
  CLEAN        si llegó a la punta de un rastro sin comida, retroceder borrándolo
  EXPLORE      explorar (seguir rastro, ir al recurso visto/recordado)
"""

WORKER_RULES = ("FLEE", "REFUEL_NEST", "EAT_MAP", "PICKUP", "GO_FEED", "CLEAN", "EXPLORE")