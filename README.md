# TurboBike

Macro externa para GTA San Andreas (1.0 US) que automatiza el glitch de velocidad en motocicletas: pulsa `Flecha Arriba` con retardos aleatorios de 35–55 ms mientras mantienes pulsada `W`.

Funciona solo por teclado: no lee procesos ni memoria del juego. Usa simulación de teclado (pydirectinput).

## Requisitos

- Windows + Python 3
- GTA San Andreas 1.0 US (`gta_sa.exe`)

## Instalación y uso

1. Abre GTA San Andreas.
2. Ejecuta `ejecutar.bat` **como administrador** (instala las dependencias y lanza la macro).

O manualmente:

```bat
pip install -r requirements.txt
python gta_sa_turbo.py
```

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
