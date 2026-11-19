# 🐜 FormicBox

**Modelo híbrido de autómata celular y agentes para la simulación de una colonia de hormigas**

Proyecto de la asignatura *Autómatas y Lenguajes Formales* — UIS.

FormicBox simula una colonia de hormigas cortadoras de hojas en un mapa 2D discreto. El **ambiente** (terreno, recursos, feromonas, fuego, humedad y clima) es un **autómata celular**; las **hormigas** son **agentes** cuyo comportamiento se modela como una **máquina de Mealy** que lee el ambiente y lo modifica. Sin control central emergen rutas de forrajeo, líneas de tráfico, defensa del nido y respuesta ante incendios e invasiones.

> **Nota de alcance:** la biología de referencia son las hormigas cortadoras de hojas (*Atta* spp.), con elementos culturales de la hormiga culona santandereana. Las castas (obreras y soldadas) corresponden funcionalmente a *Atta*; la **marabunta** es un enemigo inspirado en *Nomamyrmex esenbeckii*.

El diseño completo (fundamento biológico, reglas formales, fórmulas y parámetros) está en el [**Documento técnico**](./Entregables/Documento_técnico.docx) y en (./Entregables/Definición_formal.pdf)

El video explicativo está en el sig link https://youtu.be/P4ZoPLfAFT0 

---

## Contenido

- [Instalación y ejecución](#instalación-y-ejecución)
- [Modos de juego](#modos-de-juego)
- [Controles](#controles)
- [El modelo en resumen](#el-modelo-en-resumen)
- [Herramientas de análisis](#herramientas-de-análisis)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Arte y sonido](#arte-y-sonido)
- [Autores](#autores)

---

## Instalación y ejecución

**Requisitos:** Python 3.10 o superior.

```bash
git clone https://github.com/samueldbt/FormicBox.git
cd FormicBox
pip install -r requirements.txt   # numpy, scipy, pygame
python main.py
```

Ejecuta siempre desde la raíz del repositorio (los módulos se importan por nombre: `config`, `reglas`, `Automata`, …). SciPy acelera la difusión con convoluciones; si no está instalado se usa un cálculo equivalente con NumPy.

## Modos de juego

| Modo | Descripción |
| --- | --- |
| **Modo Dios** | Mapa aleatorio. El jugador no controla hormigas: modifica el ambiente (recursos, fuego, clima, viento, enemigos) y observa cómo responde la colonia. |
| **Lucha** | Igual que el Modo Dios, pero cada 300 ticks entra un enjambre de marabuntas por el borde del mapa. |
| **Ajustes** | Volumen general, de música y de efectos. |

La partida termina ("FIN DE LA COLONIA") cuando no quedan obreras y la colonia no tiene reservas para criar otra.

## Controles

| Tecla | Acción |
| --- | --- |
| `Espacio` | Pausa / continuar |
| `.` | Avanzar un tick (paso a paso) |
| `R` | Reiniciar con la misma semilla |
| `W` `A` `S` `D` | Cambiar la dirección del viento · `X` lo detiene |
| `V` `B` `N` `M` | Ver feromona vegetal / azúcar / alarma / caza · `Z` todas |
| `G` · `T` · `H` | Ver gradiente al nido · tráfico · humedad |
| Flechas | Mover la cámara |
| `Esc` | Volver al menú |

Con el **ratón** se usa el panel lateral: velocidad (×1, ×2, ×4), semilla siguiente y herramientas que se aplican haciendo clic en el mapa — inspeccionar celda, crear obrera/soldada/marabunta, colocar pasto, mango y bocadillo, encender fuego, lluvia, sequía, rayo, matar o quemar una hormiga — además de acciones globales: enjambre, fuego/lluvia/sequía al azar y clima automático.

## El modelo en resumen

### Ambiente (autómata celular)

Matrices de 110 × 20 celdas. Terreno: **tierra**, **piedra**, **agua** y **nido**, generado con un autómata de manchas (regla de mayoría en vecindad de Moore) a partir de una semilla. Sobre la tierra hay **pasto** (tupido/ralo, rebrota según la humedad), **mango** y **bocadillo** (objetos 2×2 con muchas "mordidas").

Cada tick, sobre el estado anterior:

1. **Feromonas** (`vegetal`, `azucar`, `alarma`, `caza`): evaporación, difusión en vecindad de Moore (convolución SciPy) y arrastre por viento:

   $$\tau' = (1-\rho)\,\tau + D\,(\bar\tau_{Moore} - \tau) + W\,(\tau_{\leftarrow viento} - \tau) + A$$

2. **Clima:** zonas de lluvia (suben la humedad y apagan fuego), sequía (la bajan) y rayos.
3. **Fuego:** cada vecino ardiendo contagia con $p = P_{base}\,e^{c\,\cos\theta}$ según el viento, puede saltar 2 celdas a favor del viento y la humedad reduce la ignición ($\times e^{-3h}$). Fuego → ceniza → tierra.
4. **Recursos:** el fuego destruye lo que toca; pasto y mango rebrotan.

### Colonia

El nido tiene una **bolsa de alimento** (1 bocadillo = 2 mango = 3 pasto = 1 unidad) de la que comen las hormigas y el **jardín fúngico**. El excedente se convierte en **crías** que tardan en desarrollarse; sin comida, las hormigas mueren de hambre. Si se acumula demasiado bocadillo, el hongo se **estresa** y las obreras dejan de buscar azúcar (salvo para comer). La **primera obrera sale sola** a explorar; el resto espera a que traiga comida, lo que favorece que se forme un único rastro claro y luego líneas de tráfico.

### Agentes (máquina de Mealy)

Cada hormiga percibe su entorno (radio 3), cambia de estado según una tabla de reglas con prioridad y produce una salida (moverse, depositar feromona, recoger, entregar, comer, morder). Se mueven en 4 direcciones eligiendo por sorteo ponderado.

| Agente | Estados | Rol |
| --- | --- | --- |
| **Obrera** | `EXPLORE` `RETURN` `FEED` `FLEE` `SEARCH` `CLEAN` | Forrajea siguiendo la pendiente del rastro, recuerda rutas, vuelve al nido, limpia rastros de fuentes agotadas, rescata botín. |
| **Soldada** | `PATROL` `ATTACK` `RESCUE` `RETURN` `FEED` `FLEE` | Patrulla cerca del nido, sigue la alarma, muerde enemigos, recupera crías robadas. |
| **Marabunta** | `RAID` `ATTACK` `RETREAT` `FLEE` | Enemigo sin nido: entra en enjambre, sigue el olor del nido y su feromona de caza, saquea comida y crías y se retira. |

La tabla de prioridades de la obrera está en [`reglas.py`](./reglas.py): `FLEE → REFUEL_NEST → EAT_MAP → LOOT → PICKUP → GO_FEED → SEARCH → CLEAN → EXPLORE`.

Todos los parámetros están en [`config.py`](./config.py).

## Herramientas de análisis

```bash
python analisis.py                 # equilibrio teórico: energía, demanda, población sostenible
python barrido.py                  # barrido de parámetros sin interfaz
python barrido.py --ticks 3000 --semillas 5 --max 60 --escenario corridor --ataque 800 --clima
```

`barrido.py` prueba combinaciones de constantes en varias semillas y las puntúa (0–100) por crecimiento de la población, formación de autopistas y rastros, y hormigas que mueren sin llegar a la comida; penaliza la extinción. Guarda `reportes/barrido_<fecha>.csv` y `.md` con las mejores y peores combinaciones. Escenarios disponibles con `--escenario`: `corridor`, `u_obstacle`, `grass_field`.

## Estructura del repositorio

```
main.py             punto de entrada
config.py           constantes y parámetros
reglas.py           tabla de reglas (máquina de Mealy) de la obrera
analisis.py         análisis de equilibrio
barrido.py          barrido de parámetros
Automata/           autómata celular: terreno, objetos, feromonas, fuego, clima, colonia, botín, escenarios
Hormigas/           agentes: base, percepción (mealy.py), obrera, soldada, marabunta
Simulación/         bucle de simulación (une autómata y agentes)
Interfaz/           pygame: escenas, render, cámara, audio, herramientas del Modo Dios
reportes/           salidas de barrido.py
```

## Arte y sonido

El juego busca su arte y audio en `Assets/` (sprites de 32 × 32 px dibujados mirando hacia arriba). Si falta un archivo, usa un sustituto de color o silencio y lo avisa en consola. Rutas esperadas (ver [`Interfaz/manifest.py`](./Interfaz/manifest.py) e [`Interfaz/audio.py`](./Interfaz/audio.py)):

- `ui/title.png` — fondo del menú
- `terrain/`, `objects/`, `fire/` — tiles (con variantes de autotile para agua, roca y pasto)
- `worker/`, `soldier/`, `marabunta/` — animaciones de caminar, cargar, atacar y morir
- `audio/music/calm.ogg`, `audio/music/fight.ogg`
- `audio/sfx/fire.ogg`, `thunder.ogg`, `bite.ogg`, `deliver.ogg`, `death.ogg`, `menu.ogg`

## Autores

Ashley, German, Consuegra, Ever, Iván, Harold, Nicolás, Angel, David, Nikollas y Samuel — *Autómatas y Lenguajes Formales*, Universidad Industrial de Santander (UIS).
