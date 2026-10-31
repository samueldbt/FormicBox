
import pygame
import numpy as np
import config
import sys

from Automata.automaton import CellularAutomaton
from Automata.terrain import DIRT, ROCK, WATER, NEST
from Automata.objects import NONE, GRASS, MANGO, BOCADILLO
from Automata.fire import ASH, BURNING

from Hormigas.worker import Worker

def create_pheromone_surface(width, height, cell_size):
    """Creates a transparent surface to overlay pheromones on the map."""
    surface = pygame.Surface((width * cell_size, height * cell_size), pygame.SRCALPHA)
    return surface

def main():
    """Main execution loop for the FormicBox simulation using Pygame."""
    pygame.init()
    
    # Initialize Display
    screen_width = config.WIDTH * config.CELL_SIZE
    screen_height = config.HEIGHT * config.CELL_SIZE
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("FormicBox - Automata & Agents")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    # Initialize Environment and Agents
    automaton = CellularAutomaton(config.WIDTH, config.HEIGHT, config.SEED)
    
    print("\n" + "=" * 50)
    print(" TERRAIN MATRIX (.: Tierra, #: Roca, ~: Agua, N: Nido)")
    print("=" * 50)
    TERRAIN_SYMBOLS = {DIRT: ".", ROCK: "#", WATER: "~", NEST: "N"}
    
    for row in automaton.terrain.matrix:
        print("".join(TERRAIN_SYMBOLS.get(val, "?") for val in row))

    print("\n" + "=" * 50)
    print(" OBJECTS MATRIX ( : Nada, \": Pasto, *: Mango)")
    print("=" * 50)
    OBJECT_SYMBOLS = {NONE: " ", GRASS: '"', MANGO: "*", BOCADILLO: "B"}
    
    for row in automaton.objects.matrix:
        print("".join(OBJECT_SYMBOLS.get(val, "?") for val in row))
        
    print("\nLas matrices se generaron correctamente. Iniciando ventana de Pygame...\n")

    colony = [Worker(automaton.terrain.nest_pos[0], automaton.terrain.nest_pos[1], automaton.terrain.nest_pos) 
              for _ in range(config.NUM_WORKERS)]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 1. Update Cellular Automaton (Pheromones, Fire, Resources)
        automaton.update_step()

        # 2. Build Occupied Mask for Traffic Prevention
        occupied_mask = np.zeros((config.HEIGHT, config.WIDTH), dtype=bool)
        for ant in colony:
            occupied_mask[ant.y, ant.x] = True

        # 3. Update Agents (Worker Logic)
        for ant in colony:
            # Free current position before moving to allow swapping/fluidity
            occupied_mask[ant.y, ant.x] = False 
            ant.update_logic(automaton, occupied_mask)
            occupied_mask[ant.y, ant.x] = True # Mark new position

        # ==========================================
        # RENDERING (Drawing the state to screen)
        # ==========================================
        screen.fill(config.COLOR_DIRT)

        # Draw Terrain, Objects, and Fire
        for y in range(config.HEIGHT):
            for x in range(config.WIDTH):
                rect = (x * config.CELL_SIZE, y * config.CELL_SIZE, config.CELL_SIZE, config.CELL_SIZE)
                terrain_type = automaton.terrain.matrix[y, x]
                fire_state = automaton.fire.matrix[y, x]
                obj_type = automaton.objects.matrix[y, x]

                # Base Terrain
                if terrain_type == ROCK:
                    pygame.draw.rect(screen, config.COLOR_ROCK, rect)
                elif terrain_type == WATER:
                    pygame.draw.rect(screen, config.COLOR_WATER, rect)
                elif terrain_type == NEST:
                    pygame.draw.rect(screen, config.COLOR_NEST, rect)
                
                # Dynamic States (Fire & Objects over Dirt)
                if terrain_type == DIRT:
                    if fire_state == BURNING:
                        pygame.draw.rect(screen, config.COLOR_FIRE, rect)
                    elif fire_state == ASH:
                        pygame.draw.rect(screen, config.COLOR_ASH, rect)
                    elif obj_type == GRASS:
                        pygame.draw.rect(screen, config.COLOR_GRASS, rect)
                    elif obj_type == MANGO:
                        pygame.draw.rect(screen, config.COLOR_MANGO, rect)
                    elif obj_type == BOCADILLO:
                        pygame.draw.rect(screen, config.COLOR_BOCADILLO, rect)

        # Draw Pheromones (Transparent overlay)
        phero_surface = create_pheromone_surface(config.WIDTH, config.HEIGHT, config.CELL_SIZE)
        veg_matrix = automaton.pheromones["vegetal"].matrix
        
        for y in range(config.HEIGHT):
            for x in range(config.WIDTH):
                if veg_matrix[y, x] > 0.1:
                    # Map concentration to alpha transparency (max 200 for visibility)
                    alpha = min(200, int(veg_matrix[y, x] * 15))
                    color = (50, 200, 50, alpha) # Greenish transparent
                    rect = (x * config.CELL_SIZE, y * config.CELL_SIZE, config.CELL_SIZE, config.CELL_SIZE)
                    pygame.draw.rect(phero_surface, color, rect)
                    
        screen.blit(phero_surface, (0, 0))

        # Draw Ants
        for ant in colony:
            center_x = (ant.x * config.CELL_SIZE) + (config.CELL_SIZE // 2)
            center_y = (ant.y * config.CELL_SIZE) + (config.CELL_SIZE // 2)
            
            # White if carrying resource, Black if empty
            color = config.COLOR_ANT_LOADED if ant.carried_resource != NONE else config.COLOR_ANT_EMPTY
            pygame.draw.circle(screen, color, (center_x, center_y), config.CELL_SIZE // 3)

        # UI Text
        info_text = font.render(f"Tick: {automaton.tick_counter} | Workers: {len(colony)}", True, (255, 255, 255))
        screen.blit(info_text, (10, 10))

        pygame.display.flip()
        clock.tick(config.FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()