from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from smbus2 import SMBus
from time import sleep

BACKSLASH_CHAR = [
    0b00000,
    0b10000,
    0b01000,
    0b00100,
    0b00010,
    0b00001,
    0b00000,
    0b00000,
]


# ----- LCD Setup -----
class LCD1602:
    def __init__(self, addr=0x3e, backlight_addr=0x6b, port=1):
        self.bus = SMBus(port)
        self.addr = addr
        self.bl_addr = backlight_addr
        self._init_lcd()

    def _send(self, data, mode):
        self.bus.write_byte_data(self.addr, mode, data)

    def _init_lcd(self):
        sleep(0.04)
        self._send(0x38, 0x00)
        self._send(0x39, 0x00)
        self._send(0x14, 0x00)
        self._send(0x70, 0x00)
        self._send(0x56, 0x00)
        self._send(0x6C, 0x00)
        sleep(0.2)
        self._send(0x38, 0x00)
        self._send(0x0C, 0x00)
        self._send(0x01, 0x00)
        sleep(0.002)
        self._init_backlight()
        self._load_custom_chars()

    def _init_backlight(self):
        # PCA9633-style LED driver: wake up, then all outputs on full
        self.bus.write_byte_data(self.bl_addr, 0x00, 0x00)  # MODE1: normal mode
        self.bus.write_byte_data(self.bl_addr, 0x08, 0xFF)  # LEDOUT: all on full
        self.bus.write_byte_data(self.bl_addr, 0x01, 0x00)  # MODE2: default

    def _load_custom_chars(self):
        self._send(0x40, 0x00)
        for byte in BACKSLASH_CHAR:
            self._send(byte, 0x40)
        self._send(0x80, 0x00)

    def clear(self):
        self._send(0x01, 0x00)
        sleep(0.002)

    def write_line(self, line: str, row: int = 0):
        if row == 1:
            self._send(0xC0, 0x00)
        for c in line[:16]:
            if c == "\\":
                self._send(0x00, 0x40)
            else:
                self._send(ord(c), 0x40)


class LCDMessage(BaseModel):
    line1: str
    line2: str = ""

# Instantiate LCD
lcd = LCD1602()
last_message: LCDMessage | None = None


# ----- FastAPI App -----
app = FastAPI()


@app.on_event("startup")
def show_waiting():
    lcd.clear()
    lcd.write_line("waiting...")


@app.post("/display")
def display_message(msg: LCDMessage):
    global last_message
    if last_message and msg.line1 == last_message.line1 and msg.line2 == last_message.line2:
        return {"status": "ok", "skipped": True, "reason": "no change"}
    lcd.clear()
    lcd.write_line(msg.line1)
    if msg.line2:
        lcd.write_line(msg.line2, row=1)
    last_message = msg
    return {"status": "ok", "displayed": msg.model_dump()}

# ----- Entrypoint -----
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)