(LAN Preferred)

* make sure both devices are connected to the same network.

type in https://(host_private_ip):1234 (must be https otherwise it will likely say it doesn't exist)

(They will be printed to the console so its not really a big deal to type it out yourself)

https://(private_ip):1234/computer - where you see the phone feed

https://(private_ip):1234/phone - where you stream from (must allow camera)


Arduino Code:
Legacy uses hobbyking reciever (HK-GT2E)
 * Future code might utilize audiojack from phone as reciever.

 - if you are curious how that will work, phone fetches sound from webpage, plays thru audiojack, audio goes thru audio biasing circuit then to analog pin on arduino.
 - audio biasing circuit just shifts audio sinewave signal above the 0 so its no longer negative, then maps it to 0-5V.

