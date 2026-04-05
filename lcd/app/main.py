from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from lib import LCD1602

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


class LCDMessage(BaseModel):
    line1: str
    line2: str = ""


# ----- LCD Setup -----
lcd = LCD1602.LCD1602(16, 2)
led = LCD1602.SN3193()
lcd.createChar(0, BACKSLASH_CHAR)
last_message: LCDMessage | None = None


def write_line(text: str, row: int = 0):
    lcd.setCursor(0, row)
    for c in text[:16]:
        if c == "\\":
            lcd.data(0x00)  # custom backslash char at CGRAM slot 0
        else:
            lcd.data(ord(c))


# ----- FastAPI App -----
app = FastAPI()


@app.on_event("startup")
def show_waiting():
    lcd.clear()
    write_line("waiting...")


@app.post("/display")
def display_message(msg: LCDMessage):
    global last_message
    if last_message and msg.line1 == last_message.line1 and msg.line2 == last_message.line2:
        return {"status": "ok", "skipped": True, "reason": "no change"}
    lcd.clear()
    write_line(msg.line1)
    if msg.line2:
        write_line(msg.line2, row=1)
    last_message = msg
    return {"status": "ok", "displayed": msg.model_dump()}

# ----- Entrypoint -----
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)
