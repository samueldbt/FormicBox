# FormicBox

# 🐜 FormicBox

**Sandbox de autómatas celulares para simular colonias de hormigas _Atta_ (arrieras / "culonas") de Santander.**

> Proyecto final de la asignatura de Autómatas Celulares. Estado: **Semana 1 – esqueleto base**.

---

## 1. ¿De qué trata?

FormicBox es un simulador 2D en vista superior, al estilo *WorldBox*, donde el **terreno es el autómata celular** y las **hormigas son agentes** que lo modifican y son modificados por él.

- **Autómata (el mundo):** una cuadrícula donde cada celda tiene un estado (pasto, agua, nido, piedra, fuego…) y niveles de feromona que se **difunden** y **se evaporan** según reglas locales de vecindad. El **viento** empuja las feromonas.
- **Agentes (las hormigas):** siguen reglas simples y locales; ninguna conoce el mapa completo. La coordinación surge de forma indirecta mediante el rastro de feromonas (**estigmergia**).
- **Modo Dios:** el usuario puede intervenir en vivo (colocar comida, iniciar fuego, aplastar hormigas) y observar cómo reacciona la colonia.

**Idea central:** estudiar cómo un comportamiento colectivo e inteligente (hallar caminos eficientes a la comida, defenderse, huir del fuego) **emerge únicamente de reglas locales**.

## 2. Mecánicas planeadas

| Elemento | Descripción |
|---|---|
| Terreno | Pasto, agua, nido y piedras; generación procedural (para que no sea siempre el mismo mapa). |
| Feromonas | Tres tipos: **Ida**, **Retorno** y **Peligro**. Difusión + evaporación + arrastre por viento. |
| Fuego | Se propaga celda a celda según los vecinos. |
| Castas | **Obreras** (cortan y transportan), **Soldadas** (atacan o huyen), **Marabuntas** (depredadoras que cazan en grupo). |
| Recursos | Pasto y *bocadillo* (super-recurso). La colonia crece según la comida recolectada. |
| HUD | Botones, sliders (viento, evaporación) y gráficas en tiempo real. |


## 3. Fundamentación biológica (hormigas *Atta*)

> **Pendiente (Grupo 4 + todos):** completar con los datos concretos que usemos para calibrar la simulación.

Puntos a cubrir:
- Qué son las *Atta* (hormigas cortadoras de hojas / arrieras, "hormiga culona" de Santander): su cultivo de hongo, castas y división del trabajo.
- Reclutamiento por feromonas de rastro y alarma (estigmergia).
- Depredadores y amenazas (marabuntas *Eciton*, fuego, inundación) y su justificación en el modelo.
- Cómo se traducen estos datos a parámetros (velocidad, evaporación, daño del fuego).


## 4. Equipo y organización

| Subgrupo | Responsabilidad | Integrantes |
|---|---|---|
| 1 | Entorno y física (autómata) | German, Consuegra, Ever |
| 2 | Agentes y biología | Iván, Harold, Nicolás Vargas |
| 3 | Pixel art, gráficos y HUD | Ángel, David |
| 4 | Integración, Modo Dios, balanceo y documentación | Nikollas, Samuel |



## 5. Hoja de ruta

- [ ] **Semana 1 – Esqueleto:** matriz, agente base, ventana gráfica, repo y detección de clics.
- [ ] Feromonas (difusión/evaporación) y seguimiento de rastros.
- [ ] Fuego, viento y castas (soldadas, marabuntas).
- [ ] HUD completo y generación procedural.
- [ ] Balanceo, documentación y entrega (**14–15 de noviembre de 2026**).

## 6. Referencias

Referencias base (**verificar y completar antes de la entrega**):

1. Grassé, P.-P. (1959). La reconstruction du nid et les coordinations interindividuelles chez *Bellicositermes natalensis* et *Cubitermes* sp. *Insectes Sociaux*, 6, 41–80. *(origen del concepto de estigmergia)*
2. Deneubourg, J.-L., Aron, S., Goss, S., & Pasteels, J. M. (1990). The self-organizing exploratory pattern of the Argentine ant. *Journal of Insect Behavior*, 3, 159–168.
3. Bonabeau, E., Dorigo, M., & Theraulaz, G. (1999). *Swarm Intelligence: From Natural to Artificial Systems*. Oxford University Press.
4. Hölldobler, B., & Wilson, E. O. (2011). *The Leafcutter Ants: Civilization by Instinct*. W. W. Norton.
5. Wolfram, S. (2002). *A New Kind of Science*. Wolfram Media.
6. _(Añadir aquí artículos sobre *Atta* en Colombia/Santander y sobre *Eciton*.)_

