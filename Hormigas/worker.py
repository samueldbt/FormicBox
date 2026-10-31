import math
import random
import config

from .ant import Ant 
from Automata.objects import NONE, GRASS, MANGO, BOCADILLO

class Worker(Ant):
    def __init__(self, y, x, nest_pos):
        """Inicializa una obrera con carga vacía y memoria de posición para forzar el flujo de tráfico."""
        super().__init__(y, x, nest_pos)
        self.carried_resource = NONE
        
        # Memoria del último paso para evitar bucles y consolidar carriles
        self.last_y = y
        self.last_x = x

    def update_logic(self, automaton, occupied_mask):
        """Ejecuta la evaluación de estado, selección de movimiento y depósito continuo de feromonas."""
        self.consume_energy()
        self._evaluate_state(automaton)
        self._move(automaton, occupied_mask)
        
        # La hormiga deposita feromonas en CADA PASO lógico si lleva un recurso
        if self.state == config.STATE_RETURN and self.carried_resource != NONE:
            self._deposit_pheromones(automaton)

    def _evaluate_state(self, automaton):
        """Actualiza el estado de la hormiga basado en peligro, energía, y recursos."""
        # Respuesta al peligro
        if automaton.pheromones["alarma"].matrix[self.y, self.x] > 0.5:
            self.state = config.STATE_FLEE
            return

        # Priorizar alimentación si la energía cae por debajo del umbral
        if self.energy < config.LOW_ENERGY_THRESHOLD and self.carried_resource == NONE:
            self.state = config.STATE_FEED

        resource_here = automaton.objects.matrix[self.y, self.x]

        # Llegó al nido para entregar recurso o recargar energía
        if (self.y, self.x) == (self.nest_y, self.nest_x):
            self.carried_resource = NONE
            self.energy = config.MAX_ENERGY
            self.state = config.STATE_EXPLORE

        # Encontró un recurso mientras exploraba o buscaba comida
        elif self.state in (config.STATE_EXPLORE, config.STATE_FEED) and resource_here != NONE:
            if self.state == config.STATE_FEED and resource_here == BOCADILLO:
                self.energy = config.MAX_ENERGY
                self.state = config.STATE_EXPLORE
            elif self.state == config.STATE_EXPLORE:
                self.carried_resource = resource_here
                self.state = config.STATE_RETURN
            
            # Consumir el objeto de la cuadrícula
            automaton.objects.matrix[self.y, self.x] = NONE

    def _move(self, automaton, occupied_mask):
        """Calcula probabilidades de movimiento evadiendo la celda anterior para generar caminos emergentes."""
        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
            
        # PREVENIR BUCLES: Eliminar la celda anterior de las opciones a menos que esté acorralada
        neighbors = []
        for ny, nx, dy, dx in all_neighbors:
            if (ny, nx) != (self.last_y, self.last_x) or len(all_neighbors) == 1:
                neighbors.append((ny, nx, dy, dx))
                
        home_angle = self.get_home_angle()
        valid_moves = []
        move_weights = []

        for ny, nx, dy, dx in neighbors:
            move_angle = math.atan2(dy, dx)
            home_alignment = math.cos(home_angle - move_angle)
            
            t_veg = automaton.pheromones["vegetal"].matrix[ny, nx]
            t_sug = automaton.pheromones["azucar"].matrix[ny, nx]
            t_alarm = automaton.pheromones["alarma"].matrix[ny, nx]
            r_fire = 1.0 if automaton.fire.matrix[ny, nx] > 0 else 0.0
            
            wv, wa, wh = 0.0, 0.0, 0.0
            
            # Asignación de pesos según la casta y el estado biológico
            if self.state == config.STATE_EXPLORE:
                wv, wa = config.WEIGHT_VEGETAL, config.WEIGHT_SUGAR
            elif self.state == config.STATE_FEED:
                wa = config.WEIGHT_SUGAR * 2.0
            elif self.state == config.STATE_RETURN:
                wh = config.WEIGHT_HOME
            elif self.state == config.STATE_FLEE:
                wh = -config.WEIGHT_HOME 

            r_val = random.random()
            
            # Ecuación central de probabilidad P
            score = (wv * t_veg) + (wa * t_sug) + (wh * home_alignment) \
                    - (config.WEIGHT_ALARM * t_alarm) - (config.WEIGHT_FIRE * r_fire) \
                    + (config.WEIGHT_RANDOM * r_val)

            # CONTRASTE MATEMÁTICO: Elevar la probabilidad al cubo para aplastar el ruido y consolidar la autopista
            final_prob = max(0.001, score) ** 3
            
            valid_moves.append((ny, nx))
            move_weights.append(final_prob)

        # Guardar la posición actual en la memoria antes de efectuar la traslación lógica
        self.last_y, self.last_x = self.y, self.x

        # Ejecutar la selección probabilística del movimiento
        chosen_move = random.choices(valid_moves, weights=move_weights, k=1)[0]
        self.y, self.x = chosen_move

    def _deposit_pheromones(self, automaton):
        """Inyecta el peso específico del recurso transportado a la capa química del autómata."""
        if self.carried_resource == GRASS:
            automaton.deposit_pheromone("vegetal", self.y, self.x, config.DEPOSIT_AMOUNT_GRASS)
        elif self.carried_resource == MANGO:
            automaton.deposit_pheromone("vegetal", self.y, self.x, config.DEPOSIT_AMOUNT_MANGO)
        elif self.carried_resource == BOCADILLO:
            automaton.deposit_pheromone("azucar", self.y, self.x, config.DEPOSIT_AMOUNT_BOCADILLO)