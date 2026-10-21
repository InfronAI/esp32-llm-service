#!/usr/bin/env python3
"""Generate private Wi-Fi, shell and API settings without writing secrets to stdout."""
import argparse
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
from project import ROOT


def make_settings(ssid, station_password, ap_ssid, host):
    if not 1 <= len(ssid.encode('utf-8')) <= 32:
        raise ValueError('Station SSID must contain 1 to 32 UTF-8 bytes')
    if not 8 <= len(station_password.encode('utf-8')) <= 63:
        raise ValueError('This setup supports WPA2 passwords of 8 to 63 UTF-8 bytes')
    if not 1 <= len(ap_ssid.encode('utf-8')) <= 32:
        raise ValueError('AP SSID must contain 1 to 32 UTF-8 bytes')
    host = str(ipaddress.IPv4Address(host))
    salt = secrets.token_hex(16)
    shell_password = 'Esp-' + secrets.token_urlsafe(12)
    ap_password = 'Wifi-' + secrets.token_urlsafe(12)
    api_key = 'esp32-' + secrets.token_hex(16)
    settings = dict(ssid=ap_ssid, wifi_password=ap_password, user='esp32', salt=salt,
                    password_hash=hashlib.sha256((salt+shell_password).encode()).hexdigest(),
                    port=23, sta_ssid=ssid, sta_password=station_password,
                    api_port=8000, api_key=api_key)
    access = dict(ssid=ap_ssid, wifi_password=ap_password, user='esp32', password=shell_password,
                  sta_ssid=ssid, base_url='http://'+host+':8000/v1', api_key=api_key,
                  model='tinystories-260k')
    return settings, access


def write_private(path, value, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if replace else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as handle:
        os.chmod(path, 0o600)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssid', help='2.4 GHz WPA2 Wi-Fi network name')
    parser.add_argument('--ap-ssid', default='ESP32-LLM')
    parser.add_argument('--host', default='192.168.4.1', help='client IP; defaults to direct AP access')
    parser.add_argument('--host-only', metavar='IP', help='update only the local client IP; retain all credentials')
    args = parser.parse_args()
    settings_path, access_path = ROOT/'device/settings.json', ROOT/'reports/access.json'
    if args.host_only:
        host = str(ipaddress.IPv4Address(args.host_only))
        access = json.loads(access_path.read_text())
        access['base_url'] = 'http://'+host+':8000/v1'
        write_private(access_path, access, replace=True)
        print('Updated client URL:', access['base_url'])
        return
    if settings_path.exists() or access_path.exists():
        parser.error('Private configuration already exists. Keep it for this board. '
                     'Use --host-only to update the client IP; back up files before reprovisioning.')
    ssid = args.ssid or input('2.4 GHz Wi-Fi SSID: ')
    password = getpass.getpass('Wi-Fi password (hidden): ')
    settings, access = make_settings(ssid, password, args.ap_ssid, args.host)
    write_private(settings_path, settings)
    write_private(access_path, access)
    print('Created device/settings.json and reports/access.json with owner-only permissions.')
    print('Read reports/access.json locally for the AP, shell and API credentials.')


if __name__ == '__main__':
    main()
