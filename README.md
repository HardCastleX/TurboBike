# TurboBike

Macro externa para GTA San Andreas (1.0 US) que automatiza el glitch de velocidad de la NRG-500: pulsa `Flecha Arriba` mientras mantienes pulsada `W`.

## Cómo funciona

El pulso va **enganchado al frame del juego**, no a un intervalo en milisegundos. GTA SA muestrea el teclado una vez por frame y el glitch premia el *flanco* de pulsación, así que el máximo teórico es un flanco cada dos frames. Un intervalo fijo en ms no puede alcanzarlo: si es más corto que un frame el pulso cae entre muestreos y se pierde el boost entero, y si es más largo se desperdician frames.

Para saber cuándo empieza un frame se lee `CTimer::m_snTimeInMilliseconds` (`0xB7CB84`), que avanza una vez por frame. Eso hace la cadencia **óptima por construcción e inmune a las variaciones de FPS**, y de paso el delta entre lecturas da los FPS reales, que se muestran en la consola. A 90 FPS son ~45 flancos por segundo, frente a los ~11 de la versión anterior basada en retardos aleatorios.

Las pulsaciones se envían con `SendInput` por scancode (la vía que leen los juegos DirectInput) y el estado de `W` se consulta con `GetAsyncKeyState`, todo directamente vía `ctypes`.

> **Nota:** el script **lee memoria del proceso del juego** (solo lectura, nunca escribe). No modifica nada, pero `OpenProcess`/`ReadProcessMemory` sobre `gta_sa.exe` es detectable por los anticheat de SA-MP y MTA. Está pensado para un jugador.

## Requisitos

- Windows + Python 3
- GTA San Andreas 1.0 US (`gta_sa.exe`)

## Instalación y uso

1. Abre GTA San Andreas.
2. Ejecuta `ejecutar.bat` (instala las dependencias y lanza la macro).

O manualmente:

```bat
pip install -r requirements.txt
python gta_sa_turbo.py
```

### ¿Hace falta administrador?

Normalmente **no**: ni el hook global de teclado, ni `SendInput`, ni leer la memoria de un proceso del mismo usuario requieren elevación. Solo lo necesitas si lanzas GTA SA como administrador (habitual con mods o con las opciones de compatibilidad de Windows): en ese caso UIPI bloquea la inyección de pulsaciones desde un proceso con menos privilegios que la ventana de destino, y el juego no responderá aunque la macro parezca funcionar. La regla es que el script esté al mismo nivel de privilegios que el juego, o por encima.

## Controles

| Tecla | Acción |
|-------|--------|
| `F11` | Activar modo turbo |
| `F12` | Desactivar modo turbo |
| `W` (mantener) | Ejecuta la macro mientras aceleras en una moto |
| `FIN (END)` | Cerrar el script |

## Archivos

- `gta_sa_turbo.py` — script principal
- `requirements.txt` / `ejecutar.bat` — instalación de dependencias
