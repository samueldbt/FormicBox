# 🐜 FormicBox

**Modelo híbrido de autómata celular y agentes para la simulación de una colonia de hormigas**

Proyecto de la asignatura *Autómatas y Lenguajes Formales*.

FormicBox es una simulación interactiva de una colonia de hormigas en un entorno bidimensional discreto. El **ambiente** (terreno, fuego, feromonas) se modela como un autómata celular, y las **hormigas** son agentes individuales que consultan y modifican ese ambiente. De reglas locales simples emerge comportamiento colectivo: rutas de forrajeo, "autopistas" de tráfico, defensa y respuesta ante incendios e invasiones.

> **Nota de alcance:** la biología de referencia son las hormigas cortadoras de hojas (*Atta* spp.), con elementos culturales de la hormiga culona santandereana. "Hormiga culona" se conserva como referencia cultural; las castas representadas corresponden funcionalmente a colonias de *Atta*.

---

## Tabla de contenido

- [Características](#características)
- [Concepto del modelo](#concepto-del-modelo)
- [El mundo](#el-mundo)
- [Autómata celular](#autómata-celular)
- [Agentes](#agentes)
- [Defensa y marabunta](#defensa-y-marabunta)
- [Fuego](#fuego)
- [Nido y jardín fúngico](#nido-y-jardín-fúngico)
- [Modo Dios](#modo-dios)
- [Representación gráfica](#representación-gráfica)
- [Arquitectura](#arquitectura)
- [Ciclo de simulación](#ciclo-de-simulación)
- [Fundamento biológico y límites del modelo](#fundamento-biológico-y-límites-del-modelo)
- [Instalación y uso](#instalación-y-uso)
- [Documentación](#documentación)

---

## Características

- Autómata celular con vecindad de Moore (8 celdas) para fuego y campos químicos.
- Cuatro campos de feromonas con difusión, evaporación y transporte por viento.
- Agentes con estados conductuales, energía individual y **vector de hogar** (integración de trayectoria) para volver al nido.
- Prevención de colisiones por evasión local: una celda nunca tiene dos hormigas.
- Tres tipos de agentes: **obreras**, **soldadas** y **marabunta** (enemigo externo).
- Memoria colectiva en el nido: el estado del jardín fúngico modifica las decisiones de forrajeo.
- Propagación de fuego direccional influida por el viento.
- **Modo Dios**: el jugador modifica el ambiente sin controlar directamente ninguna hormiga.
- Pixel-art en vista oblicua ("plano picado") con sprites interpolados entre celdas.

## Concepto del modelo

El autómata **no** representa cada hormiga como una celda. El ambiente es el componente celular; las hormigas son agentes con posición, dirección, energía, carga, estado y vector de hogar. Por eso la arquitectura es un **modelo híbrido autómata celular + agentes**.

Cada hormiga consulta información espacial cercana (feromonas, recursos, peligro, dirección del nido). La repetición de estas reglas locales produce patrones colectivos sin control central.

## El mundo

El mapa es una matriz 2D de celdas con cuatro tipos de terreno:

| Terreno | Función | Comportamiento |
| --- | --- | --- |
| **Tierra** | Superficie transitable y combustible | Puede contener recursos, fuego, ceniza y feromonas |
| **Piedra** | Obstáculo permanente | No transitable ni combustible; bloquea el fuego |
| **Agua** | Obstáculo ambiental | No transitable ni combustible; bloquea el fuego |
| **Nido** | Centro de la colonia | Agrega población, recursos y estado del jardín |

Sobre la Tierra pueden existir: **fuego**, **ceniza**, **pasto**, **mango** (recurso de alta prioridad) y **bocadillo** (recurso energético artificial).

**Estructura conceptual de una celda:**

- `tipo_terreno`: `TIERRA`, `PIEDRA`, `AGUA` o `NIDO`
- `estado_fuego`: `NINGUNO`, `FUEGO` o `CENIZA`
- `pasto`, `mango`, `bocadillo`: cantidades
- `τ_vegetal`, `τ_azucar`, `τ_alarma`, `τ_caza`: campos químicos
- `poblacion` y reservas del nido (principalmente en `NIDO`)
- `estado_hongo`: estado actual del jardín

Todas las celdas exponen los mismos campos; los que no aplican al terreno quedan en cero o `None`.

## Autómata celular

El estado de una celda depende de su estado actual, su vecindad y los parámetros del sistema:

$$S_{ij}(t+1) = F\big(S_{ij}(t),\ N_{ij}(t),\ P\big)$$

Las matrices nuevas se calculan a partir del estado anterior y se sustituyen al final del ciclo, para que el orden de recorrido no altere el resultado.

### Difusión y evaporación de feromonas

$$\tau_i^{t+1}(x,y) = (1-\rho_i)\Big[(1-D_i)\,\tau_i^{t}(x,y) + D_i\,\bar{\tau}_i^{t}(x,y)\Big] + A(x,y)$$

- `ρ`: fracción evaporada por ciclo
- `D`: factor de difusión
- `τ̄`: promedio de concentración en la vecindad de Moore
- `A`: depósito realizado por los agentes

### Transporte por viento

$$\tau' = \tau + D(\bar{\tau} - \tau) - \rho\tau + A + W(\tau)$$

`W(τ)` puede implementarse desplazando la matriz o ponderando más el vecino situado contra la dirección del viento.

### Campos químicos

| Campo | Función | Agentes |
| --- | --- | --- |
| `τ_vegetal` | Material vegetal | Obreras |
| `τ_azucar` | Bocadillo | Obreras (según estado y energía) |
| `τ_alarma` | Peligro | Obreras y soldadas |
| `τ_caza` | Cohesión de la marabunta | Enemigos |

> Anular una feromona significa retirar su peso de la función de decisión, no borrar su concentración; el rastro restante sigue decayendo por evaporación.

## Agentes

### Obreras

Población principal. Exploran, seleccionan recursos, depositan feromonas, transportan material vegetal y bocadillo, y regresan al nido con el vector de hogar.

**Estados:** `EXPLORAR` · `CARGAR` · `REGRESAR` · `ALIMENTARSE` · `HUIR`

### Selección de movimiento

$$P = w_v\,\tau_{vegetal} + w_a\,\tau_{azucar} + w_h\,H - w_d\,\tau_{alarma} - w_f\,R_{fuego} + w_r\,R$$

Los pesos cambian según el estado del agente. `H` mide la compatibilidad con el vector de hogar, `R_fuego` el riesgo de fuego y `R` aporta variación aleatoria para evitar decisiones idénticas.

### Vector de hogar

En lugar de una feromona de retorno, la hormiga conserva las coordenadas relativas del nido `H = (Hx, Hy)` y, al entrar en `REGRESAR`, calcula su dirección preferente:

$$\theta_H = \operatorname{atan2}(H_y, H_x)$$

### Energía y velocidad

La energía decrece por el coste de movimiento: `E(t+1) = E(t) − C`. Si `E < E_bajo`, la hormiga prioriza consumir bocadillo y recupera `min(E_max, E + G)`. Como adaptación lúdica, una hormiga con energía máxima obtiene un multiplicador temporal de velocidad (p. ej. 1.5×).

### Tráfico y colisiones

Una celda lógica no puede estar ocupada por dos hormigas a la vez:

1. **Detección:** se verifica si la celda destino elegida está ocupada.
2. **Evasión:** si lo está, se trata a la otra hormiga como obstáculo temporal y se recalcula hacia otro vecino disponible.
3. **Resultado:** de la evasión local emergen "autopistas" y flujos paralelos de ida y vuelta, sin carriles artificiales.

### Movimiento visual continuo

La posición lógica cambia de forma discreta, pero el sprite se interpola para evitar teletransportación:

$$x_{render} = x_0 + s(t)\,(x_1 - x_0), \qquad y_{render} = y_0 + s(t)\,(y_1 - y_0), \qquad 0 \le s(t) \le 1$$

La matriz se actualiza antes de completar la traslación (para que nadie más ocupe la celda), pero la hormiga espera a terminar la animación antes de decidir su siguiente movimiento.

## Defensa y marabunta

Marabuntas y soldadas no forrajean; sus algoritmos están diseñados para interceptación y combate.

**Marabunta (enemigo):** sigue rastros de las obreras y mantiene cohesión con `τ_caza`.

$$P_{marabunta} = w_c\,\tau_{caza} + w_p\,(\tau_{vegetal} + \tau_{azucar}) + w_r\,R$$

**Soldada (defensa):** escala el gradiente de alarma hacia el epicentro del ataque, pero huye si la alarma es por fuego.

$$P_{soldada} = w_{al}\,\tau_{alarma} - w_f\,R_{fuego} + w_r\,R$$

**Combate asimétrico** (sin dados, por superposición en celda):

- **Depredación:** una marabunta (1 HP) que entra en la celda de una obrera la elimina e inyecta valor máximo en `τ_alarma` en esa coordenada.
- **Defensa:** una soldada (5 HP) que intercepta a una marabunta la elimina y pierde 1 HP. Con 0 HP, es eliminada. Esto obliga a la marabunta a usar su densidad (`τ_caza`) para abrumar a las defensoras.

**Spawn:** la marabunta no tiene nido; aparece en los bordes del mapa en ráfagas (p. ej. 30–50 unidades), de forma procedural o activada por el jugador.

## Fuego

Secuencia: `TIERRA + combustible → FUEGO → CENIZA`. Piedra y agua bloquean la propagación.

$$P_{ignición} = \operatorname{clamp}\big[P_{base}\,(1 + c\,V\cos\theta),\ 0,\ 1\big]$$

`V` es la intensidad del viento, `θ` el ángulo entre el viento y el vecino, y `c` la influencia del viento. La probabilidad sube a favor del viento y baja en contra. *(Propuesta de diseño inspirada en modelos de fuego con autómatas celulares, no una ecuación universal.)*

**Alarma:** cuando un incendio mata a una hormiga se segrega `τ_alarma`. Las obreras priorizan salir del riesgo; las soldadas se acercan por efecto de la dispersión, pero huyen cuando la alarma supera el umbral. Un incendio grave puede activar la evacuación del nido.

## Nido y jardín fúngico

El nido agrega recursos y mantiene el estado colectivo del jardín, que actúa como **memoria de colonia**: no se guarda una lista de eventos, el estado actual modifica directamente las reglas de decisión.

```
Mango_nido(t+1)     = Mango_nido(t)     + carga_mango
Pasto_nido(t+1)     = Pasto_nido(t)     + carga_pasto
Bocadillo_nido(t+1) = Bocadillo_nido(t) + carga_bocadillo

si Bocadillo_nido ≥ U_azucar  →  estado_hongo = ESTRESADO
```

Con el jardín `ESTRESADO`, `τ_azucar` deja de pesar en el forrajeo colectivo (las obreras priorizan material vegetal), aunque una obrera con energía baja aún puede buscar bocadillo para consumo individual. Al recuperarse, las reglas vuelven progresivamente a la normalidad.

**Crecimiento poblacional** (proxy, no reproducción literal):

```
si recurso_acumulado ≥ U_crecimiento y tiempo ≥ T_crecimiento → población += 1
```

| Recurso | Tipo | Destino | Regla |
| --- | --- | --- | --- |
| Pasto | Material vegetal | Nido/jardín | Forrajeo normal |
| Mango | Material vegetal | Nido/jardín | Prioridad alta (mayor segregación de feromona) |
| Bocadillo | Energético artificial | Consumo o nido | Depende del estado del nido y la energía |

## Modo Dios

El jugador interviene el ambiente, no las hormigas:

- Colocar pasto, mango y bocadillo.
- Crear obstáculos de piedra y agua.
- Iniciar fuego.
- Modificar dirección o intensidad del viento.
- Provocar perturbaciones (p. ej. invocar marabuntas).
- Consultar estadísticas de población, recursos, feromonas y fuego.

## Representación gráfica

- Sprites y tiles en marco de **32 × 32 px**; las castas pequeñas dejan más píxeles libres dentro del marco.
- Obreras pequeñas, soldadas mayores, marabunta de tamaño similar a una obrera con mandíbulas grandes.
- Vista pixel-art oblicua / cámara alta ("plano picado").
- Las feromonas se dibujan como colores semitransparentes (un color por feromona; la opacidad indica concentración), por debajo de hormigas y objetos pero por encima de la tierra.

## Arquitectura

| Módulo | Responsabilidad | Datos |
| --- | --- | --- |
| Mapa / CA | Terreno y estados | Matriz de celdas |
| Feromonas | Difusión, evaporación y viento | Matrices τ |
| Fuego | Ignición y propagación | `estado_fuego` |
| Hormigas | Estados y movimiento | Agentes |
| Nido | Recursos, población y jardín | Estado agregado |
| Render | Sprites, interpolación y UI | Coordenadas |
| Jugador | Interacciones | Eventos |

## Ciclo de simulación

1. Leer acciones del jugador.
2. Actualizar viento.
3. Actualizar feromonas.
4. Evaluar fuego.
5. Actualizar recursos y terreno.
6. Actualizar nido.
7. Evaluar decisiones de los agentes.
8. Resolver ocupación de celdas.
9. Mover agentes (lógicamente).
10. Aplicar recolección, entrega, consumo y combate.
11. Interpolar sprites y renderizar.

## Fundamento biológico y límites del modelo

- Las *Atta* tienen división del trabajo y dependen de un hongo simbionte cultivado con material vegetal.
- La **marabunta** no es una casta de *Atta*: es un enemigo inspirado en *Nomamyrmex esenbeckii*, depredadora documentada de colonias de *Atta*.
- El **mango** tiene mayor peso de forrajeo por estudios experimentales que muestran preferencia de *Atta cephalotes* por su follaje bajo ciertas condiciones.
- El **bocadillo** es un recurso artificial del proyecto. El estrés del jardín por exceso de azúcar se inspira en el fenómeno de *delayed rejection*, pero **es una mecánica experimental del juego, no un mecanismo demostrado para *Atta***.
- La conducta de las soldadas ante el fuego, la evacuación del nido y la ecuación de ignición direccional son **reglas de simulación**, no afirmaciones sobre comportamiento real.

## Instalación y uso


**Requisitos:** ``

## Documentación

El diseño científico y técnico completo está en [`FormicBox_Documento_Tecnico.docx`](./FormicBox_Documento_Tecnico.docx).

## Autores

`<nombres del equipo>` — *Autómatas y Lenguajes Formales*, `Uis`

## Licencia

``
