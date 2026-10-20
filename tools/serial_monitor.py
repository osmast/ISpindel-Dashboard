"""Serial console for the iSpindel over USB - shows what the device does on every boot.

    python tools/serial_monitor.py                                  # auto-detect the port
    python tools/serial_monitor.py --port /dev/cu.usbserial-0001    # explicit port

Procedure:
  1. Connect the iSpindel with a DATA-capable micro-USB cable (many cables only carry power).
  2. Press the reset button TWICE within about a second - that opens the Wi-Fi config portal
     (the LED then blinks at a 1 s interval) and keeps the device awake.
  3. Watch the log here: it shows the Wi-Fi connection, the IP address, the MQTT broker it
     connects to and each value it publishes.
"""
import argparse
import glob
import sys
import time

import serial  # pyserial

PATTERNS = [
    "/dev/cu.wchusbserial*",     # CH340
    "/dev/cu.usbserial*",        # CH340 / FTDI
    "/dev/cu.SLAB_USBtoUART*",   # CP2102
    "/dev/cu.usbmodem*",
]


def find_port():
    for pattern in PATTERNS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="serial device, e.g. /dev/cu.usbserial-0001")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = args.port or find_port()
    if not port:
        print("no USB serial port found.\n"
              "  - use a DATA-capable micro-USB cable (charge-only cables never appear here)\n"
              "  - CH340 needs the WCH driver, CP2102 needs the Silicon Labs VCP driver\n"
              "  - check manually with:  ls /dev/cu.*")
        sys.exit(1)

    print(f"reading {port} at {args.baud} baud - Ctrl-C to stop\n", flush=True)
    with serial.Serial(port, args.baud, timeout=1) as ser:
        try:
            while True:
                line = ser.readline().decode(errors="replace").rstrip()
                if line:
                    print(f"{time.strftime('%H:%M:%S')} | {line}", flush=True)
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
