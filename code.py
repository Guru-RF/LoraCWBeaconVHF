# LoraCWBeacon Copyright 2023 Joeri Van Dooren (ON3URE)

import asyncio
import random
import time

import adafruit_rfm9x
import adafruit_si5351
import board
import busio
import digitalio
from microcontroller import watchdog as w
from watchdog import WatchDogMode

import config

# basic config
TEXT = config.TEXT
FREQ = config.FREQ
WPM = config.WPM
OFFSET = config.OFFSET
FSKOFFSET = config.FSKOFFSET
KEYDOWN = config.KEYDOWN
NAME = config.NAME
PAUSE = config.PAUSE
CW = config.CW
FSK = config.FSK


# configure watchdog
w.timeout = 5
w.mode = WatchDogMode.RESET
w.feed()


# Create the I2C interface.
XTAL_FREQ = 25000000
i2c = busio.I2C(scl=board.GP27, sda=board.GP26)

# PA
pa = digitalio.DigitalInOut(board.GP2)
pa.direction = digitalio.Direction.OUTPUT
pa.value = False

# PA
extpa = digitalio.DigitalInOut(board.GP0)
extpa.direction = digitalio.Direction.OUTPUT
extpa.value = False

# OSC
osc = digitalio.DigitalInOut(board.GP3)
osc.direction = digitalio.Direction.OUTPUT
osc.value = False

# leds
pwrLED = digitalio.DigitalInOut(board.GP9)
pwrLED.direction = digitalio.Direction.OUTPUT
pwrLED.value = False

txLED = digitalio.DigitalInOut(board.GP10)
txLED.direction = digitalio.Direction.OUTPUT
txLED.value = False

loraLED = digitalio.DigitalInOut(board.GP11)
loraLED.direction = digitalio.Direction.OUTPUT
loraLED.value = False


def _format_datetime(datetime):
    return "{:02}/{:02}/{} {:02}:{:02}:{:02}".format(
        datetime.tm_mon,
        datetime.tm_mday,
        datetime.tm_year,
        datetime.tm_hour,
        datetime.tm_min,
        datetime.tm_sec,
    )


def purple(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[38;5;104m[" + str(stamp) + "] " + NAME + "|" + data + "\x1b[0m"


def green(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\r\x1b[38;5;112m[" + str(stamp) + "] " + NAME + "|" + data + "\x1b[0m"


def blue(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[38;5;14m[" + str(stamp) + "] " + NAME + "|" + data + "\x1b[0m"


def yellow(data):
    return "\x1b[38;5;220m" + data + "\x1b[0m"


def red(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[1;5;31m[" + str(stamp) + "] " + NAME + "|" + data + "\x1b[0m"


def bgred(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[41m[" + str(stamp) + "] " + NAME + "|" + data + "\x1b[0m"


def setFrequency(frequency, si5351):
    xtalFreq = XTAL_FREQ
    divider = int(900000000 / frequency)
    if divider % 2:
        divider -= 1
    pllFreq = divider * frequency
    mult = int(pllFreq / xtalFreq)
    f = int(pllFreq % xtalFreq)
    f *= 1048575
    f /= xtalFreq
    num = int(f)
    denom = 1048575
    si5351.pll_a.configure_fractional(mult, num, denom)
    si5351.clock_0.configure_integer(si5351.pll_a, divider)


# setup encode and decode
encodings = {}


def encode(char):
    global encodings
    if char in encodings:
        return encodings[char]
    elif char.lower() in encodings:
        return encodings[char.lower()]
    else:
        return ""


decodings = {}


def decode(char):
    global decodings
    if char in decodings:
        return decodings[char]
    else:
        # return '('+char+'?)'
        return "¿"


def MAP(pattern, letter):
    decodings[pattern] = letter
    encodings[letter] = pattern


MAP(".-", "a")
MAP("-...", "b")
MAP("-.-.", "c")
MAP("-..", "d")
MAP(".", "e")
MAP("..-.", "f")
MAP("--.", "g")
MAP("....", "h")
MAP("..", "i")
MAP(".---", "j")
MAP("-.-", "k")
MAP(".-..", "l")
MAP("--", "m")
MAP("-.", "n")
MAP("---", "o")
MAP(".--.", "p")
MAP("--.-", "q")
MAP(".-.", "r")
MAP("...", "s")
MAP("-", "t")
MAP("..-", "u")
MAP("...-", "v")
MAP(".--", "w")
MAP("-..-", "x")
MAP("-.--", "y")
MAP("--..", "z")

MAP(".----", "1")
MAP("..---", "2")
MAP("...--", "3")
MAP("....-", "4")
MAP(".....", "5")
MAP("-....", "6")
MAP("--...", "7")
MAP("---..", "8")
MAP("----.", "9")
MAP("-----", "0")

MAP(".-.-.-", ".")  # period
MAP("--..--", ",")  # comma
MAP("..--..", "?")  # question mark
MAP("-...-", "=")  # equals, also /BT separator
MAP("-....-", "-")  # hyphen
MAP("-..-.", "/")  # forward slash
MAP(".--.-.", "@")  # at sign

MAP("-.--.", "(")  # /KN over to named station
MAP(".-.-.", "+")  # /AR stop (end of message)
MAP(".-...", "&")  # /AS wait
MAP("...-.-", "|")  # /SK end of contact
MAP("...-.", "*")  # /SN understood
MAP(".......", "#")  # error


# timing
def dit_time():
    global WPM
    PARIS = 50
    return 60.0 / WPM / PARIS


async def keyDown(si5351):
    global KEYDOWN, OFFSET, FREQ
    extpa.value = True
    pa.value = True
    setFrequency(((FREQ + OFFSET) * 1000), si5351)
    print(
        green(
            "Measured Frequency: {0:0.3f} MHz".format(
                si5351.clock_0.frequency / 1000000
            )
        )
    )
    print(green(f"Key down for {KEYDOWN} secs"))
    si5351.outputs_enabled = True
    await asyncio.sleep(KEYDOWN)
    si5351.outputs_enabled = False
    extpa.value = False
    pa.value = False
    await asyncio.sleep(1)


async def Pause():
    global PAUSE
    print(green(f"Pause for {PAUSE} secs"))
    await asyncio.sleep(PAUSE)


async def plainCW(si5351):
    global TEXT, WPM, OFFSET, FREQ
    extpa.value = True
    pa.value = True
    setFrequency(((FREQ + OFFSET) * 1000), si5351)
    print(
        green(
            "Measured Frequency: {0:0.3f} MHz".format(
                si5351.clock_0.frequency / 1000000
            )
        )
    )
    MYTEXT = TEXT
    while len(MYTEXT) != 0:
        setFrequency(((FREQ + OFFSET) * 1000), si5351)
        letter = MYTEXT[:1]
        MYTEXT = MYTEXT[1:]
        print(yellow(letter), end="")

        for sound in encode(letter):
            if sound == ".":
                si5351.outputs_enabled = True
                txLED.value = True
                await asyncio.sleep(dit_time())
                txLED.value = False
                si5351.outputs_enabled = False
                await asyncio.sleep(dit_time())
            elif sound == "-":
                si5351.outputs_enabled = True
                txLED.value = True
                await asyncio.sleep(dit_time())
                await asyncio.sleep(3 * dit_time())
                si5351.outputs_enabled = False
                txLED.value = False
                await asyncio.sleep(dit_time())
            elif sound == " ":
                await asyncio.sleep(4 * dit_time())
        await asyncio.sleep(2 * dit_time())
    print()
    extpa.value = False
    pa.value = False


async def FSKCW(si5351):
    global TEXT, WPM, OFFSET, FSKOFFSET, FREQ
    extpa.value = True
    pa.value = True
    si5351.outputs_enabled = True
    setFrequency(((FREQ + OFFSET) * 1000), si5351)
    print(
        green(
            "Measured Frequency: {0:0.3f} MHz".format(
                si5351.clock_0.frequency / 1000000
            )
        )
    )
    MYTEXT = TEXT
    while len(MYTEXT) != 0:
        setFrequency(((FREQ + OFFSET) * 1000), si5351)
        letter = MYTEXT[:1]
        MYTEXT = MYTEXT[1:]
        print(yellow(letter), end="")

        for sound in encode(letter):
            if sound == ".":
                setFrequency(((FREQ + OFFSET) * 1000), si5351)
                txLED.value = True
                await asyncio.sleep(dit_time())
                txLED.value = False
                setFrequency(((FREQ + OFFSET - FSKOFFSET) * 1000), si5351)
                await asyncio.sleep(dit_time())
            elif sound == "-":
                setFrequency(((FREQ + OFFSET) * 1000), si5351)
                txLED.value = True
                await asyncio.sleep(dit_time())
                await asyncio.sleep(3 * dit_time())
                txLED.value = False
                setFrequency(((FREQ + OFFSET - FSKOFFSET) * 1000), si5351)
                await asyncio.sleep(dit_time())
            elif sound == " ":
                setFrequency(((FREQ + OFFSET - FSKOFFSET) * 1000), si5351)
                await asyncio.sleep(4 * dit_time())
        setFrequency(((FREQ + OFFSET - FSKOFFSET) * 1000), si5351)
        await asyncio.sleep(2 * dit_time())
    si5351.outputs_enabled = False
    extpa.value = False
    pa.value = False


pwrLED.value = True
osc.value = True
time.sleep(0.5)
si5351 = adafruit_si5351.SI5351(i2c)


async def loraRunner(loop):
    await asyncio.sleep(5)
    global w
    RADIO_FREQ_MHZ = 868.000
    CS = digitalio.DigitalInOut(board.GP21)
    RESET = digitalio.DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
    rfm9x = adafruit_rfm9x.RFM9x(
        spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000, agc=False, crc=True
    )
    rfm9x.tx_power = 23
    loraTimeout = 900

    while True:
        await asyncio.sleep(0)
        # reboot weekly
        w.feed()
        timeout = int(loraTimeout) + random.randint(1, 9)
        print(
            purple(f"loraRunner: Waiting for lora packet (timeout:{timeout})"),
            end="",
        )
        # packet = rfm9x.receive(w, with_header=True, timeout=timeout)
        packet = await rfm9x.areceive(w, with_header=True, timeout=timeout)
        if packet is not None:
            if packet[:3] == (b"<\xaa\x01"):
                try:
                    rawdata = bytes(packet[3:]).decode("utf-8")
                    print(
                        purple(
                            f"loraRunner: RX: RSSI:{rfm9x.last_rssi} SNR:{rfm9x.last_snr} Data:{rawdata}"
                        )
                    )
                    loop.create_task(loraData(rawdata))
                    await asyncio.sleep(0)
                except Exception as error:
                    print(bgred(f"loraRunner: An exception occurred: {error}"))
                    print(purple("loraRunner: Lost Packet, unable to decode, skipping"))
                    continue


async def loraData(rawData):
    global TEXT, WPM, FREQ, OFFSET, FSKOFFSET, PAUSE, CALL, CW, FSK, KEYDOWN
    if rawData.startswith(f"{NAME}|text="):
        TEXT = (rawData.split("=", 1))[1]
        print(green(f"loraData: text:{TEXT}"))
    if rawData.startswith(f"{NAME}|freq="):
        FREQ = int((rawData.split("=", 1))[1])
        print(green(f"loraData: freq:{FREQ}"))
    if rawData.startswith(f"{NAME}|wpm="):
        WPM = int((rawData.split("=", 1))[1])
        print(green(f"loraData: wpm:{WPM}"))
    if rawData.startswith(f"{NAME}|pause="):
        PAUSE = int((rawData.split("=", 1))[1])
        print(green(f"loraData: pause:{PAUSE}"))
    if rawData.startswith(f"{NAME}|keydown="):
        KEYDOWN = int((rawData.split("=", 1))[1])
        print(green(f"loraData: keydown:{KEYDOWN}"))
    if rawData.startswith(f"{NAME}|offset="):
        OFFSET = float((rawData.split("=", 1))[1])
        print(green(f"loraData: offset:{OFFSET}"))
    if rawData.startswith(f"{NAME}|fskoffset="):
        FSKOFFSET = float((rawData.split("=", 1))[1])
        print(green(f"loraData: fskoffset:{FSKOFFSET}"))
    if rawData.startswith(f"{NAME}|call="):
        CALL = float((rawData.split("=", 1))[1])
        print(green(f"loraData: call:{CALL}"))
    if rawData.startswith(f"{NAME}|cw="):
        if (rawData.split("=", 1))[1] == "False":
            CW = False
        else:
            CW = True
        print(green(f"loraData: cw:{CW}"))
    if rawData.startswith(f"{NAME}|fsk="):
        if (rawData.split("=", 1))[1] == "False":
            FSK = False
        else:
            FSK = True
        print(green(f"loraData: fsk:{FSK}"))
    if rawData.startswith(f"{NAME}|writeconfig"):
        try:
            with open("/config.py", "w") as fp:
                fp.write(f"WPM = {WPM}\n")
                fp.write(f"FREQ = {FREQ}\n")
                fp.write(f"OFFSET = {OFFSET}\n")
                fp.write(f"FSKOFFSET = {FSKOFFSET}\n")
                fp.write(f'TEXT = "{TEXT}"\n')
                fp.write(f"KEYDOWN = {KEYDOWN}\n")
                fp.write(f"PAUSE = {PAUSE}\n")
                fp.write(f'NAME = "{NAME}"\n')
                fp.write(f"FSK = {FSK}\n")
                fp.write(f"CW = {CW}\n")
                fp.flush()
                print(green("loraData: wrote config"))
        except OSError as e:  # Typically when the filesystem isn't
            print(
                bgred(
                    f"loraData: An exception occurred: {e} (filesystem not available?)"
                )
            )


async def beaconRunner(si5351):
    global CW, FSK
    while True:
        await Pause()
        await keyDown(si5351)
        if CW is True:
            await plainCW(si5351)
        if FSK is True:
            await FSKCW(si5351)


async def keepAlive(w):
    while True:
        await asyncio.sleep(0)
        w.feed()


async def main():
    loop = asyncio.get_event_loop()
    beaconLoop = asyncio.create_task(beaconRunner(si5351))
    keepAliveLoop = asyncio.create_task(keepAlive(w))
    loraRunnerLoop = asyncio.create_task(loraRunner(loop))
    await asyncio.gather(beaconLoop, keepAliveLoop, loraRunnerLoop)


asyncio.run(main())
