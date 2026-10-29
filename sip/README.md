# PhoneSuite SIP test setup (Asterisk on Android)

This folder configures two **authorized test extensions** on an Asterisk instance running in Debian under Termux/PRoot. It does not install Asterisk itself and does not build the Android client.

## 1. Install/check Asterisk

In Termux:

```sh
pkg update
pkg install proot-distro
proot-distro install debian
proot-distro login debian
```

Inside Debian:

```sh
apt update
apt install asterisk
asterisk -V
```

If Debian says the package is unavailable, stop here; the server binary must be built or installed from a compatible, trusted source before continuing.

## 2. Copy this setup script into the Debian environment

From Termux, clone/download the project into a location accessible from Debian, or copy `sip/setup-asterisk-termux.sh` into Debian. Then run inside Debian:

```sh
chmod +x setup-asterisk-termux.sh
./setup-asterisk-termux.sh
```

When prompted, enter the desired password for **both** extensions. The script does not print or commit the password. You asked to use `Amecca1994!`; enter that at both prompts if you still want that value. Because it has been shared in chat, it should be treated as exposed; use a unique random password for any non-test or internet-reachable system.

The script backs up the existing Asterisk config files before appending the test configuration. If a previous PhoneSuite block exists, it stops instead of duplicating it.

## 3. Start and verify Asterisk

For a foreground diagnostic session:

```sh
asterisk -cvvvvv
```

From another Debian shell:

```sh
asterisk -rx "pjsip show transports"
asterisk -rx "pjsip show endpoints"
asterisk -rx "pjsip show contacts"
asterisk -rx "dialplan show phonesuite-internal"
```

Expected endpoints: `1001` and `1002`. A contact appears only after a client successfully registers.

## 4. Network addresses

- Same Android phone: SIP server URI can use `sip:1001@127.0.0.1:5060` if the app's SIP stack and Asterisk share the same Android network namespace.
- Second device on the same Wi-Fi: use the phone's current Wi-Fi LAN IP, not `127.0.0.1`.
- Cellular/internet access is not configured here. Do not port-forward UDP 5060 or RTP to the public internet with this starter configuration.

## 5. Important limitations

- The Asterisk server setup and the Android SIP client are separate tasks. This folder configures the server only.
- Reliable incoming calls while Android is idle require background execution, a foreground service, battery-optimization handling, and possibly push notifications.
- The UDP config is a LAN test configuration, not production security. Use strong unique credentials, firewall restrictions, and TLS/SRTP before exposing any service.
- Android/PRoot may suspend or terminate Asterisk when the app is backgrounded.
