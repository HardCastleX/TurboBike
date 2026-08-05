# -*- coding: utf-8 -*-
"""
Macro externa para GTA San Andreas (gta_sa.exe).
Automatiza el glitch de velocidad de la NRG-500 pulsando 'Flecha Arriba'
mientras se mantiene pulsada W.

El pulso va enganchado al frame del juego, no a un intervalo en milisegundos:
GTA SA muestrea el teclado una vez por frame y el glitch premia el flanco de
pulsacion, asi que el maximo teorico es un flanco cada dos frames. Para saber
cuando empieza un frame se lee CTimer::m_snTimeInMilliseconds (0xB7CB84), que
avanza una vez por frame. Eso hace la cadencia optima por construccion e inmune
a las variaciones de FPS, y el delta entre lecturas da los FPS reales.

Las pulsaciones se envian con SendInput por scancode (via ctypes) y el estado de
W se consulta con GetAsyncKeyState.

Requisitos (Windows):
    pip install -r requirements.txt
    (o simplemente ejecuta ejecutar.bat, que instala todo automaticamente)

No hace falta ejecutarlo como administrador: ni el hook global de teclado, ni
SendInput, ni leer la memoria de un proceso del mismo usuario lo requieren. Solo
es necesario si lanzas GTA SA como administrador (mods u opciones de
compatibilidad), porque Windows (UIPI) impide inyectar pulsaciones en una
ventana con mas privilegios que el proceso que las envia.

Direcciones validas para GTA SA 1.0 US (base fija 0x400000, sin ASLR).

Controles:
    F11 -> activa el modo turbo
    F12 -> desactiva el modo turbo
    W (mantener pulsada) -> ejecuta la macro
    FIN (END) -> cierra el script
"""

import ctypes
import os
import sys
import threading
import time
import traceback
from ctypes import wintypes

import keyboard

HOTKEY_TURBO_ON = "F11"
HOTKEY_TURBO_OFF = "F12"
TECLA_ACCION = "w"
HOTKEY_SALIR = "end"

PROCESOS_JUEGO = ("gta_sa.exe", "gta-sa.exe")

# --- Direcciones de GTA SA 1.0 US -----------------------------------------
DIR_TIMER_FRAME = 0xB7CB84  # CTimer::m_snTimeInMilliseconds: avanza 1 vez/frame
DIR_MS_POR_SEGUNDO = 0xB7015C  # ms por segundo de juego (1000 por defecto)

INTERVALO_POLL = 0.0005  # 0.5 ms: latencia maxima al detectar el frame nuevo
TIMEOUT_FRAME = 0.25  # sin frames nuevos en 250 ms -> menu, alt-tab o juego cerrado
INTERVALO_FPS = 0.25  # cada cuanto se refresca el contador de FPS en pantalla
INTERVALO_CHEQUEO_PROCESO = 0.5  # cada cuanto se comprueba que el juego sigue vivo

ERROR_LOG = "error.log"

ANCHO = 52  # ancho interior del recuadro, en caracteres

# Paleta ANSI del layout
C_RESET = "\033[0m"
C_MARCO = "\033[38;5;240m"  # gris oscuro para bordes y separadores
C_TITULO = "\033[1;38;5;208m"  # naranja para el titulo
C_TECLA = "\033[1;38;5;39m"  # cian para las teclas
C_TEXTO = "\033[38;5;250m"  # gris claro para las descripciones
C_DATO = "\033[38;5;245m"  # gris para el contador de FPS
C_OFF = "\033[38;5;244m"
C_ESPERA = "\033[38;5;220m"
C_ON = "\033[1;38;5;46m"
C_AVISO = "\033[38;5;203m"

# Estados del indicador: (color, simbolo, texto)
ESTADO_SIN_JUEGO = (C_AVISO, "!", "Esperando gta_sa.exe")
ESTADO_FALLO = (C_AVISO, "x", "Fallo interno: revisa error.log")
ESTADO_OFF = (C_OFF, "o", "Turbo desactivado")
ESTADO_ESPERA = (C_ESPERA, "*", "Turbo activado  ~  en espera de W")
ESTADO_ACELERANDO = (C_ON, "#", "Turbo activado  ~  ACELERANDO")

# Lineas impresas debajo de la linea de estado (borde inferior + hueco final)
LINEAS_TRAS_ESTADO = 3


# --------------------------------------------------------------------------
# Entrada nativa: SendInput por scancode (lo que leen los juegos DirectInput)
# y GetAsyncKeyState para consultar W. Evita el overhead por pulsacion de
# pydirectinput y el reparseo de nombres de tecla de keyboard.is_pressed().
# --------------------------------------------------------------------------

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = wintypes.WPARAM

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

SCANCODE_ARRIBA = 0x48  # flecha arriba: scancode extendido
VK_ACCION = ord(TECLA_ACCION.upper())  # 'w' -> 0x57


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT
_user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_user32.GetAsyncKeyState.restype = ctypes.c_short


def _crear_input(scancode, keyup):
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY
    if keyup:
        flags |= KEYEVENTF_KEYUP
    return INPUT(
        type=INPUT_KEYBOARD,
        union=_INPUTUNION(ki=_KEYBDINPUT(wVk=0, wScan=scancode, dwFlags=flags)),
    )


# Estructuras preconstruidas: se reutilizan en cada pulsacion, no se recrean
_INPUT_ARRIBA_DOWN = _crear_input(SCANCODE_ARRIBA, keyup=False)
_INPUT_ARRIBA_UP = _crear_input(SCANCODE_ARRIBA, keyup=True)
_TAMANO_INPUT = ctypes.sizeof(INPUT)

_arriba_pulsada = False


def _enviar(evento):
    """Envia un evento de teclado ya preparado mediante SendInput."""
    _user32.SendInput(1, ctypes.byref(evento), _TAMANO_INPUT)


def alternar_arriba():
    """Invierte el estado de Flecha Arriba. Un flanco cada dos frames."""
    global _arriba_pulsada
    _arriba_pulsada = not _arriba_pulsada
    _enviar(_INPUT_ARRIBA_DOWN if _arriba_pulsada else _INPUT_ARRIBA_UP)


def soltar_arriba():
    """Garantiza que Flecha Arriba queda suelta (pausa, salida, W liberada)."""
    global _arriba_pulsada
    if _arriba_pulsada:
        _arriba_pulsada = False
        _enviar(_INPUT_ARRIBA_UP)


def tecla_accion_pulsada():
    """True si W esta fisicamente pulsada (bit alto de GetAsyncKeyState)."""
    return _user32.GetAsyncKeyState(VK_ACCION) & 0x8000 != 0


# --------------------------------------------------------------------------
# Lectura de memoria del proceso del juego (solo lectura, sin escrituras)
# --------------------------------------------------------------------------

TH32CS_SNAPPROCESS = 0x0002
HANDLE_INVALIDO = ctypes.c_void_p(-1).value  # INVALID_HANDLE_VALUE
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_kernel32.ReadProcessMemory.argtypes = (
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
_kernel32.ReadProcessMemory.restype = wintypes.BOOL
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.OpenProcess.restype = wintypes.HANDLE
# Sin declarar restype, ctypes asume c_int y truncaria los handles en 64 bits
_kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
_kernel32.Process32FirstW.restype = wintypes.BOOL
_kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
_kernel32.Process32NextW.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
_kernel32.GetStdHandle.restype = wintypes.HANDLE


def buscar_pid_juego():
    """Devuelve el PID de gta_sa.exe, o None si no esta en ejecucion."""
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == HANDLE_INVALIDO:
        return None
    try:
        entrada = PROCESSENTRY32W()
        entrada.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not _kernel32.Process32FirstW(snapshot, ctypes.byref(entrada)):
            return None
        objetivos = {nombre.lower() for nombre in PROCESOS_JUEGO}
        while True:
            if entrada.szExeFile.lower() in objetivos:
                return entrada.th32ProcessID
            if not _kernel32.Process32NextW(snapshot, ctypes.byref(entrada)):
                return None
    finally:
        _kernel32.CloseHandle(snapshot)


class Juego:
    """Handle de lectura sobre el proceso del juego."""

    def __init__(self, handle):
        self._handle = handle
        # Punteros y funcion enlazados una sola vez: leer_u32 se llama ~1700
        # veces por segundo y crear los byref en cada llamada costaba un 32% mas
        self._rpm = _kernel32.ReadProcessMemory
        self._buffer = wintypes.DWORD()
        self._p_buffer = ctypes.byref(self._buffer)
        self._leidos = ctypes.c_size_t()
        self._p_leidos = ctypes.byref(self._leidos)
        self._punteros = {}

    @classmethod
    def conectar(cls):
        pid = buscar_pid_juego()
        if pid is None:
            return None
        # Solo hace falta VM_READ: ReadProcessMemory no necesita mas permisos
        handle = _kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
        return cls(handle) if handle else None

    def leer_u32(self, direccion):
        """Lee 4 bytes; None si el proceso murio o la direccion no es valida."""
        puntero = self._punteros.get(direccion)
        if puntero is None:
            puntero = self._punteros[direccion] = ctypes.c_void_p(direccion)
        ok = self._rpm(self._handle, puntero, self._p_buffer, 4, self._p_leidos)
        if not ok or self._leidos.value != 4:
            return None
        return self._buffer.value

    def cerrar(self):
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None


# --------------------------------------------------------------------------
# Registro de errores y eventos
# --------------------------------------------------------------------------


def registrar_excepcion(exc_info, origen):
    """Escribe una excepcion en error.log sin tocar la consola."""
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Origen: {origen}\n")
        traceback.print_exception(*exc_info, file=f)


def registrar_error(exc_info, origen):
    """Escribe una excepcion no controlada en error.log y la muestra."""
    registrar_excepcion(exc_info, origen)
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
_estado = None
_extra = ""
_lock_estado = threading.Lock()
_layout_inicializado = False


# --------------------------------------------------------------------------
# Layout de consola
# --------------------------------------------------------------------------


def mostrar_estado(estado, extra=""):
    """Reescribe en su sitio la linea de estado del recuadro."""
    global _estado, _extra
    with _lock_estado:
        if not _layout_inicializado or (estado == _estado and extra == _extra):
            return
        _estado, _extra = estado, extra
        color, simbolo, texto = estado
        izquierda = f"  {simbolo}  {texto}"
        derecha = f"{extra}  " if extra else ""
        relleno = " " * max(0, ANCHO - len(izquierda) - len(derecha))
        sys.stdout.write(
            f"\033[{LINEAS_TRAS_ESTADO}F\033[2K"
            f"  {C_MARCO}|{C_RESET}{color}{izquierda}{C_RESET}{relleno}"
            f"{C_DATO}{derecha}{C_RESET}{C_MARCO}|{C_RESET}"
            f"\033[{LINEAS_TRAS_ESTADO}E"
        )
        sys.stdout.flush()


def habilitar_vt():
    """Activa las secuencias ANSI conservando el resto de flags de la consola."""
    handle = _kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    modo = wintypes.DWORD()
    if not _kernel32.GetConsoleMode(handle, ctypes.byref(modo)):
        return  # salida redirigida a un archivo o pipe: no hay consola que ajustar
    _kernel32.SetConsoleMode(handle, modo.value | 0x0004)  # VIRTUAL_TERMINAL_PROCESSING


def dibujar_layout():
    """Imprime el encabezado, la leyenda de teclas y el marco del estado."""
    barra = "-" * ANCHO
    teclas = (
        (HOTKEY_TURBO_ON, "activar modo turbo"),
        (HOTKEY_TURBO_OFF, "desactivar modo turbo"),
        (TECLA_ACCION.upper(), "manten pulsada para acelerar"),
        (HOTKEY_SALIR.upper(), "salir"),
    )

    print()
    print(f"  {C_MARCO}.{barra}.{C_RESET}")
    print(
        f"  {C_MARCO}|{C_RESET}{C_TITULO}{'XCELERATE  ~  GTA SA TURBO'.center(ANCHO)}"
        f"{C_RESET}{C_MARCO}|{C_RESET}"
    )
    print(f"  {C_MARCO}'{barra}'{C_RESET}")
    print()
    for tecla, descripcion in teclas:
        print(f"   {C_TECLA}[{tecla.center(5)}]{C_RESET}  {C_TEXTO}{descripcion}{C_RESET}")
    print()
    print(f"  {C_MARCO}.{barra}.{C_RESET}")
    print()  # linea de estado, se rellena en mostrar_estado()
    print(f"  {C_MARCO}'{barra}'{C_RESET}")
    print()


# --------------------------------------------------------------------------
# Macro
# --------------------------------------------------------------------------


def activar_turbo():
    global turbo_activo
    turbo_activo = True


def desactivar_turbo():
    global turbo_activo
    turbo_activo = False


class ContadorFps:
    """Promedia los deltas del timer del juego para mostrar FPS reales."""

    def __init__(self):
        self._suma_ms = 0
        self._frames = 0
        self._ultimo_refresco = 0.0
        self.texto = ""

    def registrar(self, delta_ms):
        self._suma_ms += delta_ms
        self._frames += 1
        ahora = time.perf_counter()
        if ahora - self._ultimo_refresco < INTERVALO_FPS:
            return
        self._ultimo_refresco = ahora
        if self._suma_ms > 0:
            self.texto = f"{self._frames * 1000 / self._suma_ms:.0f} FPS"
        self._suma_ms = 0
        self._frames = 0

    def limpiar(self):
        self._suma_ms = 0
        self._frames = 0
        self.texto = ""


def esperar_frame_nuevo(juego, anterior):
    """Bloquea hasta que el timer del juego avanza.

    Devuelve el valor nuevo, o None si se agota TIMEOUT_FRAME (pausa o proceso
    cerrado) o si el script esta cerrandose.
    """
    limite = time.perf_counter() + TIMEOUT_FRAME
    while _ejecutando:
        valor = juego.leer_u32(DIR_TIMER_FRAME)
        if valor is None or valor != anterior:
            return valor
        if time.perf_counter() > limite:
            return None
        time.sleep(INTERVALO_POLL)
    return None


def bucle_principal():
    juego = None
    fps = ContadorFps()
    anterior = None
    acelerando = False
    ultimo_chequeo = 0.0

    while _ejecutando:
        if juego is None:
            juego = Juego.conectar()
            if juego is None:
                soltar_arriba()
                fps.limpiar()
                mostrar_estado(ESTADO_SIN_JUEGO)
                time.sleep(0.5)
                continue
            comprobar_escala_tiempo(juego)
            acelerando = False

        if not (turbo_activo and tecla_accion_pulsada()):
            soltar_arriba()
            acelerando = False
            mostrar_estado(ESTADO_ESPERA if turbo_activo else ESTADO_OFF, fps.texto)
            time.sleep(0.005)
            # En reposo no hace falta sondear el timer: basta comprobar de vez en
            # cuando que el proceso sigue vivo para que la pantalla no mienta
            ahora = time.perf_counter()
            if ahora - ultimo_chequeo >= INTERVALO_CHEQUEO_PROCESO:
                ultimo_chequeo = ahora
                if juego.leer_u32(DIR_TIMER_FRAME) is None:
                    juego.cerrar()
                    juego = None
            continue

        if not acelerando:
            # Transicion reposo -> acelerando: hay que partir de un valor fresco
            # del timer, o el primer pulso caeria a mitad de frame
            anterior = juego.leer_u32(DIR_TIMER_FRAME)
            if anterior is None:
                juego.cerrar()
                juego = None
                continue
            acelerando = True

        nuevo = esperar_frame_nuevo(juego, anterior)
        if nuevo is None:
            # Sin frames nuevos (menu, alt-tab o juego cerrado): soltar la tecla
            # para no dejarla pegada y volver a evaluar en la siguiente vuelta.
            soltar_arriba()
            if not _ejecutando:
                break
            fps.limpiar()
            acelerando = False
            mostrar_estado(ESTADO_ESPERA if turbo_activo else ESTADO_OFF)
            if juego.leer_u32(DIR_TIMER_FRAME) is None:  # el proceso ya no esta
                juego.cerrar()
                juego = None
            continue

        # Frame nuevo: invertir Flecha Arriba. Un flanco cada dos frames.
        alternar_arriba()
        fps.registrar(max(0, nuevo - anterior))
        anterior = nuevo
        mostrar_estado(ESTADO_ACELERANDO, fps.texto)

    soltar_arriba()
    if juego is not None:
        juego.cerrar()


def ejecutar_macro():
    """Envuelve el bucle: un fallo aqui no debe morir en silencio.

    Sin esto, una excepcion en el hilo dejaba la macro muerta con la consola
    mostrando un estado normal, sin rastro en error.log.
    """
    try:
        bucle_principal()
    except Exception:
        registrar_excepcion(sys.exc_info(), "bucle de la macro")
        soltar_arriba()
        mostrar_estado(ESTADO_FALLO)


def comprobar_escala_tiempo(juego):
    """Avisa si el juego no corre a 1000 ms por segundo (calculo de FPS falseado)."""
    ms_por_segundo = juego.leer_u32(DIR_MS_POR_SEGUNDO)
    if ms_por_segundo not in (None, 1000):
        registrar_evento(
            f"Aviso: ms por segundo = {ms_por_segundo} (esperado 1000); "
            "el contador de FPS no sera fiable"
        )


def main():
    global _ejecutando, _layout_inicializado

    habilitar_vt()
    sys.stdout.write("\033[2J\033[H")  # limpia sin lanzar un proceso (cls)

    registrar_evento(f"Inicio del script (PID {os.getpid()})")

    keyboard.add_hotkey(HOTKEY_TURBO_ON, activar_turbo)
    keyboard.add_hotkey(HOTKEY_TURBO_OFF, desactivar_turbo)

    hilo = threading.Thread(target=ejecutar_macro, daemon=True)
    hilo.start()

    dibujar_layout()
    with _lock_estado:
        _layout_inicializado = True

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
    soltar_arriba()  # red de seguridad si el hilo no llego a limpiar
    try:
        keyboard.unhook_all()
    except Exception as e:
        registrar_error(sys.exc_info(), "keyboard.unhook_all()")


if __name__ == "__main__":
    main()
