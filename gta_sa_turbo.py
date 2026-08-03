# -*- coding: utf-8 -*-
"""
Macro externa para GTA San Andreas (gta_sa.exe).
Automatiza el glitch de velocidad en motocicletas pulsando 'Flecha Arriba'
mientras se mantiene pulsada W, con retardos aleatorios entre 35 y 55 ms
tanto al mantener la tecla pulsada (KeyDown) como al soltarla (KeyUp).

Funciona por teclado unicamente: no lee procesos ni memoria del juego.

Requisitos (Windows):
    pip install -r requirements.txt
    (o simplemente ejecuta ejecutar.bat, que instala todo automaticamente)

Ejecutar como administrador (el hook global de teclado lo requiere).

Controles:
    F11 -> activa el modo turbo
    F12 -> desactiva el modo turbo
    W (mantener pulsada) -> ejecuta la macro
    FIN (END) -> cierra el script
"""

import ctypes
import os
import random
import sys
import threading
import time
import traceback

import keyboard
import pydirectinput

pydirectinput.PAUSE = 0  # sin pausa extra: los retardos los controla la macro

HOTKEY_TURBO_ON = "F11"
HOTKEY_TURBO_OFF = "F12"
TECLA_ACCION = "w"
HOTKEY_SALIR = "end"

DELAY_MIN = 0.035  # 35 ms
DELAY_MAX = 0.055  # 55 ms

ERROR_LOG = "error.log"


def registrar_error(exc_info, origen):
    """Escribe una excepcion no controlada en error.log y la muestra."""
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Origen: {origen}\n")
        traceback.print_exception(*exc_info, file=f)
    sys.__excepthook__(*exc_info)


def registrar_evento(mensaje):
    """Registra un evento de ciclo de vida (inicio, fin, heartbeat) en error.log."""
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}\n")


def excepthook_global(exc_type, exc_value, exc_tb):
    # Ctrl+C (KeyboardInterrupt) no es un fallo: es la forma normal de cerrar
    if exc_type is KeyboardInterrupt:
        return
    registrar_error((exc_type, exc_value, exc_tb), "hilo principal")


sys.excepthook = excepthook_global

turbo_activo = False
_ejecutando = True
_estado = ""


def mostrar_estado(texto):
    global _estado
    if texto != _estado:
        _estado = texto
        sys.stdout.write("\033[F\033[K" + texto + "\n")
        sys.stdout.flush()


def activar_turbo():
    global turbo_activo
    if not turbo_activo:
        turbo_activo = True
        mostrar_estado("Modo turbo: activado (en espera de W)")


def desactivar_turbo():
    global turbo_activo
    if turbo_activo:
        turbo_activo = False
        mostrar_estado("Modo turbo: desactivado")


def bucle_principal():
    global _ejecutando
    while _ejecutando:
        if turbo_activo and keyboard.is_pressed(TECLA_ACCION):
            mostrar_estado("\033[92mModo turbo: activado: acelerando\033[0m")
            pydirectinput.keyDown("up")
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            pydirectinput.keyUp("up")
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        else:
            if turbo_activo:
                mostrar_estado("Modo turbo: activado (en espera de W)")
            else:
                mostrar_estado("Modo turbo: desactivado")
            time.sleep(0.01)


def main():
    global _ejecutando

    os.system("cls")

    registrar_evento(f"Inicio del script (PID {os.getpid()})")

    ctypes.windll.kernel32.SetConsoleMode(
        ctypes.windll.kernel32.GetStdHandle(-11), 7
    )

    keyboard.add_hotkey(HOTKEY_TURBO_ON, activar_turbo)
    keyboard.add_hotkey(HOTKEY_TURBO_OFF, desactivar_turbo)

    hilo = threading.Thread(target=bucle_principal, daemon=True)
    hilo.start()

    print("Macro GTA SA lista.")
    print(f"  {HOTKEY_TURBO_ON} -> activar modo turbo")
    print(f"  {HOTKEY_TURBO_OFF} -> desactivar modo turbo")
    print(f"  Manten {TECLA_ACCION.upper()} para ejecutar la macro")
    print(f"  {HOTKEY_SALIR.upper()} -> salir")
    mostrar_estado("Modo turbo: desactivado")

    try:
        keyboard.wait(HOTKEY_SALIR)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[!] El hook de teclado fallo: {e}")
        registrar_error(sys.exc_info(), "keyboard.wait()")
    registrar_evento("Salida limpia por FIN o Ctrl+C")
    _ejecutando = False
    hilo.join(timeout=2.0)
    try:
        keyboard.unhook_all()
    except Exception as e:
        registrar_error(sys.exc_info(), "keyboard.unhook_all()")


if __name__ == "__main__":
    main()
