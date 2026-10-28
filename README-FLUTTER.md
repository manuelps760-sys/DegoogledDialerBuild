# Degoogled Dialer — Flutter rebuild

This is a clean Flutter-first rebuild in branch `flutter-rebuild`. The UI is Flutter; Android Telecom integration stays native Kotlin.

## Current MVP
- Flutter dial pad and phone/SIP sections.
- Native Android default-dialer role request.
- Native Telecom `placeCall` bridge with fallback to Android's system dialer.
- Native `InCallService` notification actions for answer/reject/hang up.
- Explicit status that SIP registration/media are not implemented yet; no fake connection state.

## Build in Termux
Install Flutter and Android SDK/command-line tools in Termux using a supported Termux package/source for your device. Then:
```sh
pkg update
pkg install git openjdk-17
git clone -b flutter-rebuild https://github.com/manuelps760-sys/DegoogledDialerBuild.git
cd DegoogledDialerBuild
flutter doctor -v
flutter pub get
flutter analyze
flutter build apk --debug
```
Flutter/Android SDK setup on-device can be fragile and may require substantial storage and memory. The GitHub Actions workflow builds the same source in a clean cloud environment and uploads a debug APK artifact.

## Install
The APK is a debug build, not a Play Store release. After build, install the artifact and manually choose it under Android Settings > Apps > Default apps > Phone app. Confirm system permission prompts. Do not use for emergency calling until fully tested.

## Not yet implemented / verified
- SIP registration, authentication, incoming SIP INVITE, SIP dialog/ACK/BYE, codec negotiation, STUN/TURN/ICE, SRTP, and two-way media.
- Real-device verification of Telecom call handling, audio routing, Bluetooth, call waiting, and Android-version behavior.
- Contacts and call-history UI.
