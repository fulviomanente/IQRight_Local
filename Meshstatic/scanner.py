# mobile.py
import board
import busio
import digitalio
import time
import argparse
import adafruit_rfm9x
from meshstatic import logger, MeshNode
import random

def init_radio(freq, cs_pin, reset_pin):
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs = digitalio.DigitalInOut(cs_pin)
    reset = digitalio.DigitalInOut(reset_pin)
    rfm = adafruit_rfm9x.RFM9x(spi, cs, reset, freq)
    rfm.tx_power = 20
    return rfm

def main():
    parser = argparse.ArgumentParser(description="Meshstatic Mobile node (end device)")
    parser.add_argument("--node-id", type=int, required=True, help="numeric id")
    parser.add_argument("--server-id", type=int, default=1, help="server/gateway node id")
    parser.add_argument("--freq", type=float, default=915.0)
    parser.add_argument("--cs", type=int, default=8)
    parser.add_argument("--reset", type=int, default=25)
    parser.add_argument("--interval", type=float, default=10.0, help="telemetry interval seconds")
    args = parser.parse_args()

    cs_pin = board.CE1
    reset_pin = board.D25

    rfm = init_radio(args.freq, cs_pin, reset_pin)
    node = MeshNode(rfm, node_id=args.node_id)

    def on_msg(pkt, rssi):
        # handle incoming command from server or broadcast
        print(f"[MOBILE {node.node_id}] RX src={pkt['src']} seq={pkt['seq']} rssi={rssi} payload={pkt['payload']}")

    node.on_message = on_msg
    node.start_receiving(forward_enabled=False)

    try:
        while True:
            # simple telemetry payload: battery / gps placeholder
            telemetry = {
                "temp": round(20 + random.random()*10, 2),
                "battery": round(3.5 + random.random()*0.8, 2),
                "seq_note": "telemetry"
            }
            payload = str(telemetry)
            # unicast to server and await ack
            ok = node.send_unicast(args.server_id, payload, await_ack=True)
            print(f"Sent telemetry to {args.server_id} ack={ok} rssi={getattr(rfm,'last_rssi',None)}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()

if __name__ == "__main__":
    main()
