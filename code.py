# LoraCWBeacon Copyright 2023 Joeri Van Dooren (ON3URE)

import time
import board
import digitalio
import busio
from digitalio import DigitalInOut, Direction, Pull
import adafruit_si5351
import config

# User config
WPM = config.WPM
FREQ = config.FREQ
OFFSET = config.OFFSET
BEACON = config.BEACON
BEACONDELAY = config.BEACONDELAY

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


pwrLED.value = True
    
osc.value = True
    
time.sleep(0.5)

delay = " " * BEACONDELAY
cwBeacon = BEACON + delay
    
# Turn on the variable osc
#osc.value = True
si5351 = adafruit_si5351.SI5351(i2c)
#si5351.outputs_enabled = True
#time.sleep(2)


while True:
    extpa.value = True
    pa.value = True
    setFrequency(((FREQ+OFFSET)*1000), si5351)
    print('Measured Frequency: {0:0.3f} MHz'.format(si5351.clock_0.frequency/1000000))
    print('Key down for 15secs')
    si5351.outputs_enabled = True
    time.sleep(15)
    si5351.outputs_enabled = False
    time.sleep(1)
    while len(cwBeacon) is not 0:
        letter = cwBeacon[:1]
        cwBeacon = cwBeacon[1:]
        print(letter, end="")

        for sound in encode(letter):
            if sound == '.':
                si5351.outputs_enabled = True
                txLED.value = True
                time.sleep(dit_time())
                txLED.value = False
                si5351.outputs_enabled = False
                time.sleep(dit_time())
            elif sound == '-':
                si5351.outputs_enabled = True
                txLED.value = True
                time.sleep(dit_time())
                time.sleep(3*dit_time())
                si5351.outputs_enabled = False
                txLED.value = False
                time.sleep(dit_time())
            elif sound == ' ':
                time.sleep(4*dit_time())
        time.sleep(2*dit_time())

    pa.value = False
    extpa.value = False

    #osc.value = False
    delay = " " * BEACONDELAY
    cwBeacon = BEACON + delay
    print()