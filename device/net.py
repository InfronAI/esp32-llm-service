"""Shared AP + station setup for the shell and local inference server."""
import json
import network
import time

_ap = None


def setup():
    global _ap
    if _ap is not None:
        return _ap
    with open('/settings.json') as handle:
        config = json.load(handle)
    network.hostname('esp32-llm')
    ap = network.WLAN(network.WLAN.IF_AP)
    ap.active(True)
    ap.config(ssid=config['ssid'], security=3, key=config['wifi_password'], max_clients=2)
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '192.168.4.1'))
    sta = network.WLAN(network.WLAN.IF_STA)
    if config.get('sta_ssid'):
        sta.active(True)
        sta.config(reconnects=-1, pm=network.WLAN.PM_NONE)
        if not sta.isconnected():
            sta.connect(config['sta_ssid'], config['sta_password'])
        deadline = time.ticks_add(time.ticks_ms(), 20000)
        while not sta.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            time.sleep_ms(200)
        print('Wi-Fi station:', config['sta_ssid'], sta.ifconfig()[0], 'status', sta.status())
    _ap = ap
    return ap


def status():
    sta = network.WLAN(network.WLAN.IF_STA)
    return {'connected': sta.isconnected(), 'ip': sta.ifconfig()[0],
            'ap_ip': '192.168.4.1', 'hostname': 'esp32-llm'}
