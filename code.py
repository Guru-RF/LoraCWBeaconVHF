# LoraCWBeacon Copyright 2023 Joeri Van Dooren (ON3URE)

import time
import board
import digitalio
import busio
from digitalio import DigitalInOut, Direction, Pull
import adafruit_si5351
import config
import asyncio
import adafruit_gps
import adafruit_rfm9x

# User config
WPM = config.WPM
FREQ = config.FREQ
BEACON = config.BEACON
BEACONDELAY = config.BEACONDELAY

# Create the I2C interface.
XTAL_FREQ = 24000000
i2c = busio.I2C(scl=board.GP27, sda=board.GP26)

# PA
pa = digitalio.DigitalInOut(board.GP2)
pa.direction = digitalio.Direction.OUTPUT
pa.value = False

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

def setFrequency(frequency, si5351):
    xtalFreq = XTAL_FREQ
    divider = int(900000000 / frequency)
    if (divider % 2): divider -= 1
    pllFreq = divider * frequency
    mult = int(pllFreq / xtalFreq)
    l = int(pllFreq % xtalFreq)
    f = l
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
        return ''


decodings = {}
def decode(char):
    global decodings
    if char in decodings:
        return decodings[char]
    else:
        #return '('+char+'?)'
        return '¿'


def MAP(pattern,letter):
    decodings[pattern] = letter
    encodings[letter ] = pattern
    
MAP('.-'   ,'a') ; MAP('-...' ,'b') ; MAP('-.-.' ,'c') ; MAP('-..'  ,'d') ; MAP('.'    ,'e')
MAP('..-.' ,'f') ; MAP('--.'  ,'g') ; MAP('....' ,'h') ; MAP('..'   ,'i') ; MAP('.---' ,'j')
MAP('-.-'  ,'k') ; MAP('.-..' ,'l') ; MAP('--'   ,'m') ; MAP('-.'   ,'n') ; MAP('---'  ,'o')
MAP('.--.' ,'p') ; MAP('--.-' ,'q') ; MAP('.-.'  ,'r') ; MAP('...'  ,'s') ; MAP('-'    ,'t')
MAP('..-'  ,'u') ; MAP('...-' ,'v') ; MAP('.--'  ,'w') ; MAP('-..-' ,'x') ; MAP('-.--' ,'y')
MAP('--..' ,'z')
              
MAP('.----','1') ; MAP('..---','2') ; MAP('...--','3') ; MAP('....-','4') ; MAP('.....','5')
MAP('-....','6') ; MAP('--...','7') ; MAP('---..','8') ; MAP('----.','9') ; MAP('-----','0')

MAP('.-.-.-','.') # period
MAP('--..--',',') # comma
MAP('..--..','?') # question mark
MAP('-...-', '=') # equals, also /BT separator
MAP('-....-','-') # hyphen
MAP('-..-.', '/') # forward slash
MAP('.--.-.','@') # at sign

MAP('-.--.', '(') # /KN over to named station
MAP('.-.-.', '+') # /AR stop (end of message)
MAP('.-...', '&') # /AS wait
MAP('...-.-','|') # /SK end of contact
MAP('...-.', '*') # /SN understood
MAP('.......','#') # error


# timing
def dit_time():
    global WPM
    PARIS = 50 
    return 60.0 / WPM / PARIS

async def loraLoop():
    while True:
        await asyncio.sleep(10)
        print("test")

async def beaconLoop():
    global cwBeacon
    global BEACON
    global FREQ
    delay = " " * BEACONDELAY
    cwBeacon = BEACON + delay
    while True:
        # Turn on the variable osc
        #osc.value = True
        await asyncio.sleep(3)
        si5351 = adafruit_si5351.SI5351(i2c)
        await asyncio.sleep(1)
        setFrequency((FREQ*1000), si5351)
        print('Measured Frequency: {0:0.3f} MHz'.format(si5351.clock_0.frequency/1000000))
        si5351.outputs_enabled = True
        await asyncio.sleep(1)

        pa.value = True
        await asyncio.sleep(1)
        while len(cwBeacon) is not 0:
            letter = cwBeacon[:1]
            cwBeacon = cwBeacon[1:]
            print(letter, end="")

            for sound in encode(letter):
                if sound == '.':
                    si5351.outputs_enabled = True
                    txLED.value = True
                    await asyncio.sleep(dit_time())
                    txLED.value = False
                    si5351.outputs_enabled = False
                    await asyncio.sleep(dit_time())
                elif sound == '-':
                    si5351.outputs_enabled = True
                    txLED.value = True
                    await asyncio.sleep(dit_time())
                    await asyncio.sleep(3*dit_time())
                    si5351.outputs_enabled = False
                    txLED.value = False
                    await asyncio.sleep(dit_time())
                elif sound == ' ':
                    await asyncio.sleep(4*dit_time())
            await asyncio.sleep(2*dit_time())
        pa.value = False

        #osc.value = False
        delay = " " * BEACONDELAY
        cwBeacon = BEACON + delay
        print()
        await asyncio.sleep(0)


async def main():
    # GPS Module (uart)
    uart = busio.UART(board.GP4, board.GP5, baudrate=9600, timeout=10, receiver_buffer_size=1024)
    gps = adafruit_gps.GPS(uart, debug=False) 

    # Set GPS pps to always (without lock) to 24Mhz
    Speed = bytes ([
        0xB5, 0x62, 0x06, 0x31, 0x20, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x36, 0x6E, 0x01,
  0x00, 0x00, 0x00, 0x80, 0x00, 0x00, 0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x6F, 0x00, 0x00, 0x00, 0x6D, 0x8D,
    ])
    gps.send_command(Speed)
    time.sleep(0.1)

    # Wait for PPS fix
    while not gps.fix_quality is 2:
        pwrLED.value = True
        time.sleep(0.5)
        try:
            gps.update()
        except MemoryError:
            # the gps module has a nasty memory leak just ignore and reload (Gps trackings stays in tact)
            supervisor.reload()

        pwrLED.value = False
        time.sleep(0.5)
        print(gps.fix_quality)

    pwrLED.value = True
        
    osc.value = True
        
    time.sleep(0.5)

    # LoRa APRS frequency
    RADIO_FREQ_MHZ = 433.775
    CS = digitalio.DigitalInOut(board.GP21)
    RESET = digitalio.DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)

    # Lora Module
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000)
    rfm9x.tx_power = config.LORAPOWER # 5 min 23 max

    #loop = asyncio.get_event_loop()
    #loraL = asyncio.create_task(loraLoop())
    cwL = asyncio.create_task(beaconLoop())
    await asyncio.gather(cwL)


asyncio.run(main()) 
