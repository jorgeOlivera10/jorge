# Normativa Pain&Gain 26/27

> Reglas de la liga. Se guardan aquí porque afectan directamente al modelo
> económico (primas, cesiones, retos) y a la contabilidad de dinero **real**
> (fianza, castigos por jornada). Referenciadas desde `src/biwenger/rules.py`.

## Dinero real (€) — contabilidad externa a Biwenger

- **Fianza:** 30 € (se pierde si se incumple la normativa o se abandona).
- **Entrada:** 30 €.
- **Castigo por jornada** (se cobra al terminar la competición, sin límite de pérdidas):
  - Último clasificado de la jornada: **3 €**
  - Penúltimo: **2 €**
  - Antepenúltimo: **1 €**
- **Regla 15:** quien acumule 30 € en pérdidas debe volver a pagar la fianza para continuar.

## Reglas (in-game salvo que se indique)

1. Prohibido dejar dinero a otro jugador en negativo para que pueda puntuar en la jornada.
2. Importe **mínimo de cesión: 200.000 €**, pagado antes de comenzar la jornada.
3. Prohibido pactar transacciones entre competidores para subir cláusulas.
4. Un jugador clausulado/comprado por otro no se puede devolver al anterior propietario por un valor igual o mayor.
5. Prohibido vender a precio anormal (muy bajo/alto) para favorecer a otro (a votación).
6. **Máximo de cesiones que puede recibir un jugador por jornada: 2.**
7. **Retos:** 2 por semana, apostando **máximo 1 M** por reto.
8. **Primas por clasificación** (in-game, se mantienen respecto a la temporada pasada):
   - 1.º: **1 M**
   - 2.º: **500 k**
   - 3.º: **250 k**
   - **500 k** por jugador en el **once ideal** de la jornada.
   - **750 k** por alinear al **MVP** de la jornada.
9. Si no se vende / no se pone a vender a los futbolistas antes de iniciar la jornada, esa jornada no puntúan.
10. Si un jugador abandona la liga, no podrá volver a entrar.
11. **Máximo de jugadores que se pueden ceder en una jornada: 3.**
12. Las **3 últimas jornadas**: prohibida la cesión y la compra/venta entre usuarios.
13. Un jugador no puede venderse a su antiguo propietario hasta que pasen **10 días** desde la compra.
14. **Precio máximo por cesión: 1 M.**
15. Ver arriba (reset de fianza a 30 € acumulados en pérdidas).

## Implicaciones para la herramienta

- **Motor económico:** las **cesiones** (200 k–1 M) y **retos** (≤1 M) mueven saldo in-game
  entre managers; hay que detectarlos en el tablón y sumarlos/restarlos. Las **primas**
  (`roundFinished`) se leen del tablón y pueden validarse contra los valores de arriba.
- **Pain tracker (dinero real):** a partir de la clasificación por jornada (`rounds/league`)
  se calcula quién quedó último / penúltimo / antepenúltimo y se acumula el marcador
  de €, aplicando el reset de fianza de la regla 15.
