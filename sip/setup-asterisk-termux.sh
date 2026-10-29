#!/usr/bin/env bash
set -euo pipefail

# Run inside the Debian environment started by proot-distro, not in Android's
# outer Termux shell. This script never stores a SIP password in Git.
if ! command -v asterisk >/dev/null 2>&1; then
  echo "Asterisk is not installed in this Debian environment."
  echo "Try: apt update && apt install asterisk"
  exit 1
fi

PJSIP="/etc/asterisk/pjsip.conf"
DIALPLAN="/etc/asterisk/extensions.conf"
MARKER="; BEGIN PHONESUITE SIP EXTENSIONS"

if grep -Fq "$MARKER" "$PJSIP" 2>/dev/null; then
  echo "PhoneSuite SIP configuration already exists in $PJSIP."
  echo "No changes made. Edit the existing block manually if needed."
  exit 1
fi

read -r -s -p "Enter the SIP password to use for BOTH extensions 1001 and 1002: " SIP_PASS
echo
if [ -z "$SIP_PASS" ]; then
  echo "Password cannot be empty."
  exit 1
fi
read -r -s -p "Confirm SIP password: " SIP_PASS2
echo
if [ "$SIP_PASS" != "$SIP_PASS2" ]; then
  echo "Passwords do not match."
  exit 1
fi

# Prevent config injection through pasted values.
case "$SIP_PASS" in
  *$'\n'*|*$'\r'*|*';'*)
    echo "Password contains a character not supported by this setup script."
    exit 1
    ;;
esac

STAMP="$(date +%Y%m%d-%H%M%S)"
cp -a "$PJSIP" "$PJSIP.backup.$STAMP"
cp -a "$DIALPLAN" "$DIALPLAN.backup.$STAMP"

cat >> "$PJSIP" <<EOF

$MARKER
[transport-phonesuite]
type=transport
protocol=udp
bind=0.0.0.0:5060

[1001]
type=endpoint
context=phonesuite-internal
disallow=all
allow=ulaw
auth=auth1001
aors=1001
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes

[auth1001]
type=auth
auth_type=userpass
username=1001
password=$SIP_PASS

[1001]
type=aor
max_contacts=2
remove_existing=yes

[1002]
type=endpoint
context=phonesuite-internal
disallow=all
allow=ulaw
auth=auth1002
aors=1002
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes

[auth1002]
type=auth
auth_type=userpass
username=1002
password=$SIP_PASS

[1002]
type=aor
max_contacts=2
remove_existing=yes
; END PHONESUITE SIP EXTENSIONS
EOF

cat >> "$DIALPLAN" <<'EOF'

; BEGIN PHONESUITE SIP DIALPLAN
[phonesuite-internal]
exten => 1001,1,Dial(PJSIP/1001,30)
 same => n,Hangup()
exten => 1002,1,Dial(PJSIP/1002,30)
 same => n,Hangup()
; END PHONESUITE SIP DIALPLAN
EOF

unset SIP_PASS SIP_PASS2
echo "Configuration added. Password was not printed."
echo "Restart Asterisk to ensure the new transport is loaded:"
echo "  asterisk -rx 'core restart now'"
echo "Then check:"
echo "  asterisk -rx 'pjsip show transports'"
echo "  asterisk -rx 'pjsip show endpoints'"
echo "  asterisk -rx 'dialplan show phonesuite-internal'"
echo
echo "Security: this starter config uses SIP/UDP and is intended for a trusted LAN only."
