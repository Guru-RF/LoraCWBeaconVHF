import board
import digitalio
import storage
import usb_cdc

btn = digitalio.DigitalInOut(board.GP15)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

# Disable devices only if dah/dit is not pressed.
if btn.value is True:
    print("boot: button not pressed, disabling drive")
    storage.disable_usb_drive()
    storage.remount("/", readonly=False)

    usb_cdc.enable(console=True, data=False)
else:
    print("boot: button pressed, enable console, enabling drive")

    usb_cdc.enable(console=True, data=False)

    new_name = "VHFBCN"
    storage.remount("/", readonly=False)
    m = storage.getmount("/")
    m.label = new_name
    storage.remount("/", readonly=True)
