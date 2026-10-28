from pathlib import Path
import sys

root = Path(sys.argv[1])
base = root / "app/src/main/java/org/degoogled/dialer"
main = base / "MainActivity.kt"
sip = base / "sip/SipClient.kt"
debug = base / "SipDebugManager.kt"
radio = base / "RadioDiagnosticsActivity.kt"
manifest = root / "app/src/main/AndroidManifest.xml"

if not all(p.exists() for p in [main, sip, debug, radio, manifest]):
    raise SystemExit("The uploaded v5 ZIP has an unexpected layout.")

main.write_text("""package org.degoogled.dialer

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import org.degoogled.dialer.sip.SipClient

class MainActivity : AppCompatActivity() {
    private lateinit var etDisplay: EditText
    private lateinit var etSipServer: EditText
    private lateinit var etSipUser: EditText
    private lateinit var etSipPass: EditText
    private lateinit var tvSipStatus: TextView
    private var sipClient: SipClient? = null
    private var sipRegistered = false
    private var pendingNumber: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        etDisplay = findViewById(R.id.etNumberDisplay)
        etSipServer = findViewById(R.id.etSipServer)
        etSipUser = findViewById(R.id.etSipUser)
        etSipPass = findViewById(R.id.etSipPass)
        tvSipStatus = findViewById(R.id.tvSipStatus)
        handleDialIntent(intent)

        sipClient = SipClient(this).apply {
            onStatusChanged = { status ->
                tvSipStatus.text = "Status: " + status
                sipRegistered = status.startsWith("Registered")
            }
            onCallConnected = { startActivity(Intent(this@MainActivity, InCallActivity::class.java)) }
            onCallEnded = { tvSipStatus.text = "Status: Call ended" }
        }

        setupKeypad()
        findViewById<Button>(R.id.btnSipRegister).setOnClickListener {
            val server = etSipServer.text.toString().trim()
            val user = etSipUser.text.toString().trim()
            val pass = etSipPass.text.toString()
            if (server.isBlank() || user.isBlank() || pass.isBlank()) {
                Toast.makeText(this, "Enter your SIP server, username, and password first.", Toast.LENGTH_LONG).show()
            } else {
                sipClient?.startClient(server, user, pass, SipDebugManager.pcapEnabled)
            }
        }
        findViewById<Button>(R.id.btnCall).setOnClickListener {
            val target = etDisplay.text.toString().trim()
            if (target.isBlank()) {
                Toast.makeText(this, "Enter a phone number or SIP extension.", Toast.LENGTH_SHORT).show()
            } else if (sipRegistered) {
                sipClient?.makeCall(target, SipDebugManager.selectedCodecPayloadType)
            } else {
                pendingNumber = target
                if (checkSelfPermission(Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
                    placeCellularCall(target)
                } else {
                    requestPermissions(arrayOf(Manifest.permission.CALL_PHONE), 702)
                }
            }
        }
        findViewById<Button>(R.id.btnLaunchDevSettings).setOnClickListener {
            startActivity(Intent(this, DeveloperSettingsActivity::class.java))
        }
        findViewById<Button>(R.id.btnLaunchRadioDiag).setOnClickListener {
            startActivity(Intent(this, RadioDiagnosticsActivity::class.java))
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleDialIntent(intent)
    }

    private fun handleDialIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_DIAL) {
            val number = intent.data?.schemeSpecificPart
            if (!number.isNullOrBlank()) etDisplay.setText(number)
        }
    }

    private fun placeCellularCall(number: String) {
        try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.fromParts("tel", number, null)))
        } catch (_: Exception) {
            Toast.makeText(this, "Could not start the call. Check call permission and phone service.", Toast.LENGTH_LONG).show()
        }
        pendingNumber = null
    }

    @Deprecated("Deprecated API retained for device compatibility")
    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(code, permissions, results)
        if (code == 702) {
            val number = pendingNumber
            if (results.isNotEmpty() && results[0] == PackageManager.PERMISSION_GRANTED && !number.isNullOrBlank()) {
                placeCellularCall(number)
            } else {
                Toast.makeText(this, "Call permission was not granted.", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun setupKeypad() {
        val ids = intArrayOf(R.id.btn0, R.id.btn1, R.id.btn2, R.id.btn3, R.id.btn4, R.id.btn5,
            R.id.btn6, R.id.btn7, R.id.btn8, R.id.btn9, R.id.btnStar, R.id.btnHash)
        for (id in ids) {
            findViewById<Button>(id).setOnClickListener { view ->
                val digit = (view as Button).text.toString()
                etDisplay.append(digit)
                if (digit.isNotEmpty()) DtmfPlayer.playTone(digit[0])
                checkSecretCodeTrigger(etDisplay.text.toString())
            }
        }
        findViewById<Button>(R.id.btnBackspace).setOnClickListener {
            val text = etDisplay.text.toString()
            if (text.isNotEmpty()) etDisplay.setText(text.dropLast(1))
        }
    }

    private fun checkSecretCodeTrigger(input: String) {
        when (input) {
            "*#*#338#*#*", "*#*#DEV#*#*" -> {
                etDisplay.setText("")
                startActivity(Intent(this, DeveloperSettingsActivity::class.java))
            }
            "*#06#" -> Toast.makeText(this,
                "Open Android Settings → About phone for the real device identifier. This app does not invent IMEI values.",
                Toast.LENGTH_LONG).show()
            "*#*#4636#*#*" -> startActivity(Intent(this, RadioDiagnosticsActivity::class.java))
        }
    }

    override fun onDestroy() {
        sipClient?.stopClient()
        super.onDestroy()
    }
}
""")

s = sip.read_text()
s = s.replace('var sipServer: String = "192.168.1.100"', 'var sipServer: String = ""')
s = s.replace('var sipUser: String = "101"', 'var sipUser: String = ""')
s = s.replace('var sipPass: String = "secret123"', 'var sipPass: String = ""')
s = s.replace('import java.net.InetAddress', 'import java.net.InetAddress\nimport java.net.Inet4Address\nimport java.net.NetworkInterface')
s = s.replace('''    private fun getLocalIpAddress(): String {
        return "127.0.0.1"
    }''', '''    private fun getLocalIpAddress(): String {
        return try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (!iface.isUp || iface.isLoopback) continue
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()
                    if (address is Inet4Address && !address.isLoopbackAddress && !address.isLinkLocalAddress) {
                        return address.hostAddress ?: "0.0.0.0"
                    }
                }
            }
            "0.0.0.0"
        } catch (_: Exception) { "0.0.0.0" }
    }''')
sip.write_text(s)

d = debug.read_text()
d = d.replace("var pcapEnabled: Boolean = true", "var pcapEnabled: Boolean = false")
d = d.replace("# Default SIPS over TLS", "// Default SIPS over TLS")
d = d.replace("# Default Secure RTP payload encryption", "// SRTP is experimental and disabled by default")
d = d.replace("var useSrtp: Boolean = true", "var useSrtp: Boolean = false")
debug.write_text(d)

radio.write_text(r"""package org.degoogled.dialer

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.telephony.TelephonyManager
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class RadioDiagnosticsActivity : AppCompatActivity() {
    private lateinit var tvMetrics: TextView
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_radio_diagnostics)
        tvMetrics = findViewById(R.id.tvRadioMetrics)
        findViewById<Button>(R.id.btnRefreshMetrics).setOnClickListener { refreshMetrics() }
        refreshMetrics()
    }
    @Suppress("DEPRECATION")
    private fun refreshMetrics() {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork
        val caps = if (network != null) cm.getNetworkCapabilities(network) else null
        val transport = when {
            caps == null -> "No active network"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "Cellular data"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "VPN"
            else -> "Other / unknown"
        }
        val validated = caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true
        val carrier = try {
            val tm = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            tm.networkOperatorName.takeIf { it.isNotBlank() } ?: "Unavailable"
        } catch (_: SecurityException) { "Restricted by Android" }
          catch (_: Exception) { "Unavailable" }
        tvMetrics.text = "=== Device Network Diagnostics ===\n" +
            "Android: " + android.os.Build.VERSION.RELEASE + " (API " + android.os.Build.VERSION.SDK_INT + ")\n" +
            "Active connection: " + transport + "\n" +
            "Internet validated: " + (if (validated) "Yes" else "No / unknown") + "\n" +
            "Carrier name: " + carrier + "\n\n" +
            "Detailed signal, cell ID, VoLTE and IMS information is not exposed to every ordinary app. " +
            "This screen reports only available system information; it does not invent readings or claim to block IMSI catchers."
    }
}
""")

m = manifest.read_text()
# Declare only capabilities used by the dialer; Android still enforces role and runtime consent.
permissions = [
    # Calling, Telecom, contact and call-history integration.
    "android.permission.MODIFY_AUDIO_SETTINGS",
    "android.permission.WAKE_LOCK",
    "android.permission.VIBRATE",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.ANSWER_PHONE_CALLS",
    "android.permission.READ_PHONE_NUMBERS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    # VoIP foreground audio and notification behavior.
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_MICROPHONE",
    "android.permission.POST_NOTIFICATIONS",
    # Bluetooth headset routing (Android 12+).
    "android.permission.BLUETOOTH_CONNECT",
]
for permission in permissions:
    line = f'    <uses-permission android:name="{permission}" />'
    if line not in m:
        m = m.replace("</manifest>", line + "\n</manifest>")
# Legacy Bluetooth and storage permissions are capped to old Android versions.
legacy_permissions = [
    ('android.permission.BLUETOOTH', 30),
    ('android.permission.BLUETOOTH_ADMIN', 30),
    ('android.permission.READ_EXTERNAL_STORAGE', 32),
    ('android.permission.WRITE_EXTERNAL_STORAGE', 28),
]
for permission, max_sdk in legacy_permissions:
    line = f'    <uses-permission android:name="{permission}" android:maxSdkVersion="{max_sdk}" />'
    if line not in m:
        m = m.replace("</manifest>", line + "\n</manifest>")
if "android.permission.MODIFY_AUDIO_SETTINGS" not in m:
    m = m.replace('<uses-permission android:name="android.permission.RECORD_AUDIO" />',
        '<uses-permission android:name="android.permission.RECORD_AUDIO" />\n    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />')
manifest.write_text(m)


# Register as a genuine Android dialer candidate; role approval remains user-controlled.
m = manifest.read_text()
dial_filter = '''            <intent-filter>
                <action android:name="android.intent.action.DIAL" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:scheme="tel" />
            </intent-filter>'''
if 'android:scheme="tel"' not in m:
    needle = '''                <action android:name="android.intent.action.DIAL" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>'''
    if needle in m:
        m = m.replace(needle, needle + "\n" + dial_filter, 1)
service_needle = '''        <service
            android:name=".CustomInCallService"
            android:permission="android.permission.BIND_INCALL_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.telecom.InCallService" />
            </intent-filter>
        </service>'''
service_real = '''        <service
            android:name=".CustomInCallService"
            android:permission="android.permission.BIND_INCALL_SERVICE"
            android:exported="true">
            <meta-data android:name="android.telecom.IN_CALL_SERVICE_UI" android:value="true" />
            <meta-data android:name="android.telecom.IN_CALL_SERVICE_RINGING" android:value="false" />
            <intent-filter>
                <action android:name="android.telecom.InCallService" />
            </intent-filter>
        </service>'''
if service_needle in m:
    m = m.replace(service_needle, service_real, 1)
manifest.write_text(m)

main_text = main.read_text()
if "import android.app.role.RoleManager" not in main_text:
    main_text = main_text.replace("import android.Manifest", "import android.Manifest\nimport android.app.role.RoleManager\nimport android.os.Build", 1)
if "requestDialerRoleIfNeeded()" not in main_text:
    main_text = main_text.replace("        setContentView(R.layout.activity_main)", "        setContentView(R.layout.activity_main)\n        requestDialerRoleIfNeeded()", 1)
    role_method = '''
    private fun requestDialerRoleIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = getSystemService(RoleManager::class.java) ?: return
            if (roleManager.isRoleAvailable(RoleManager.ROLE_DIALER) &&
                !roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) {
                startActivityForResult(
                    roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER),
                    703
                )
            }
        }
    }

'''
    main_text = main_text.replace("    private fun setupKeypad() {", role_method + "    private fun setupKeypad() {", 1)
main.write_text(main_text)

print("Source improvements applied.")


# Wire carrier-call controls to Android Telecom instead of UI-only toggles.
service = base / "CustomInCallService.kt"
service.write_text(r'''package org.degoogled.dialer

import android.content.Intent
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log

class CustomInCallService : InCallService() {
    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        activeCall = call
        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                Log.d("InCallService", "Call state=" + state)
                if (state == Call.STATE_DISCONNECTED && activeCall === call) activeCall = null
            }
        })
        try {
            startActivity(Intent(this, InCallActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        } catch (e: Exception) {
            Log.w("InCallService", "Unable to launch in-call screen", e)
        }
    }
    override fun onCallRemoved(call: Call) {
        if (activeCall === call) activeCall = null
        super.onCallRemoved(call)
    }
    companion object {
        @Volatile var activeCall: Call? = null
    }
}
''')

incall = base / "InCallActivity.kt"
incall.write_text(r'''package org.degoogled.dialer

import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.degoogled.dialer.rtp.RtpAudioEngine

class InCallActivity : AppCompatActivity() {
    private lateinit var metrics: TextView
    private lateinit var record: Button
    private lateinit var mute: Button
    private lateinit var speaker: Button
    private lateinit var normal: Button
    private lateinit var deep: Button
    private lateinit var helium: Button
    private lateinit var robot: Button
    private lateinit var anon: Button
    private val handler = Handler(Looper.getMainLooper())
    private var updating = false
    private var recording = false
    private var muted = false
    private var speakerOn = false
    private var recorder: CallRecorder? = null
    private val audio by lazy { getSystemService(AUDIO_SERVICE) as AudioManager }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_incall)
        metrics = findViewById(R.id.tvRtpMetrics)
        record = findViewById(R.id.btnRecordCall)
        mute = findViewById(R.id.btnMuteCall)
        speaker = findViewById(R.id.btnSpeakerCall)
        normal = findViewById(R.id.btnVoiceNormal)
        deep = findViewById(R.id.btnVoiceDeep)
        helium = findViewById(R.id.btnVoiceHelium)
        robot = findViewById(R.id.btnVoiceRobot)
        anon = findViewById(R.id.btnVoiceAnon)
        recorder = CallRecorder(this)
        setupEffects()

        record.setOnClickListener {
            if (CustomInCallService.activeCall != null) {
                Toast.makeText(this, "Android does not expose carrier-call audio to this recorder.", Toast.LENGTH_LONG).show()
            } else if (!recording) {
                try {
                    recorder?.startRecording("voip-mic")
                    recording = true
                    record.text = "Stop Recording"
                    Toast.makeText(this, "Microphone recording started. Obtain any required consent.", Toast.LENGTH_LONG).show()
                } catch (e: Exception) {
                    Toast.makeText(this, "Recording unavailable: " + e.message, Toast.LENGTH_LONG).show()
                }
            } else {
                val file = recorder?.stopRecording()
                recording = false
                record.text = "Record Mic"
                Toast.makeText(this, "Saved: " + (file?.name ?: "recording stopped"), Toast.LENGTH_LONG).show()
            }
        }
        mute.setOnClickListener {
            muted = !muted
            try {
                audio.isMicrophoneMute = muted
                mute.text = if (muted) "Unmute" else "Mute"
            } catch (e: Exception) {
                muted = !muted
                Toast.makeText(this, "Mute failed: " + e.message, Toast.LENGTH_LONG).show()
            }
        }
        speaker.setOnClickListener {
            speakerOn = !speakerOn
            try {
                @Suppress("DEPRECATION")
                run { audio.isSpeakerphoneOn = speakerOn }
                speaker.text = if (speakerOn) "Earpiece" else "Speaker"
            } catch (e: Exception) {
                speakerOn = !speakerOn
                Toast.makeText(this, "Audio routing failed: " + e.message, Toast.LENGTH_LONG).show()
            }
        }
        findViewById<Button>(R.id.btnEndCall).setOnClickListener {
            if (recording) {
                recorder?.stopRecording()
                recording = false
            }
            val call = CustomInCallService.activeCall
            if (call != null) call.disconnect() else RtpAudioEngine.stopAudio()
            finish()
        }
    }

    private fun setupEffects() {
        val entries = listOf(
            Pair(normal, VoiceChanger.Mode.NORMAL),
            Pair(deep, VoiceChanger.Mode.DEEP_PITCH),
            Pair(helium, VoiceChanger.Mode.HELIUM_PITCH),
            Pair(robot, VoiceChanger.Mode.ROBOT),
            Pair(anon, VoiceChanger.Mode.ANONYMIZER)
        )
        for ((button, mode) in entries) {
            button.setOnClickListener {
                VoiceChanger.currentMode = mode
                highlightEffect(mode)
                Toast.makeText(this, "Selected " + mode.label + " (outgoing VoIP only)", Toast.LENGTH_SHORT).show()
            }
        }
        highlightEffect(VoiceChanger.currentMode)
    }

    private fun highlightEffect(mode: VoiceChanger.Mode) {
        val active = ContextCompat.getColor(this, R.color.primary_accent)
        val inactive = ContextCompat.getColor(this, R.color.dark_surface)
        val foreground = ContextCompat.getColor(this, R.color.text_primary)
        val buttons = mapOf(
            VoiceChanger.Mode.NORMAL to normal,
            VoiceChanger.Mode.DEEP_PITCH to deep,
            VoiceChanger.Mode.HELIUM_PITCH to helium,
            VoiceChanger.Mode.ROBOT to robot,
            VoiceChanger.Mode.ANONYMIZER to anon
        )
        for ((itemMode, button) in buttons) {
            button.setBackgroundColor(if (itemMode == mode) active else inactive)
            button.setTextColor(foreground)
        }
    }

    private fun refreshMetrics() {
        val call = CustomInCallService.activeCall
        val callState = when (call?.state) {
            Call.STATE_RINGING -> "Carrier call: ringing"
            Call.STATE_DIALING -> "Carrier call: dialing"
            Call.STATE_ACTIVE -> "Carrier call: active"
            Call.STATE_HOLDING -> "Carrier call: held"
            Call.STATE_DISCONNECTED -> "Carrier call: disconnected"
            else -> if (RtpAudioEngine.isStreaming) "VoIP media: running" else "No active media stream"
        }
        val codec = if (SipDebugManager.selectedCodecPayloadType == 0) "PCMU (G.711u)" else "PCMA (G.711a)"
        val security = if (RtpAudioEngine.isEncryptedSrtp) "SRTP flag set; encryption is not verified" else "RTP unencrypted"
        metrics.text = callState + "\nVoice effect: " + VoiceChanger.currentMode.label +
            "\nCodec setting: " + codec + "\nSecurity: " + security +
            "\nRTP packets sent: " + RtpAudioEngine.packetsSent
    }

    private val ticker = object : Runnable {
        override fun run() {
            if (!updating) return
            refreshMetrics()
            handler.postDelayed(this, 1000)
        }
    }
    override fun onResume() {
        super.onResume()
        updating = true
        handler.post(ticker)
    }
    override fun onPause() {
        updating = false
        handler.removeCallbacks(ticker)
        super.onPause()
    }
    override fun onDestroy() {
        if (recording) recorder?.stopRecording()
        super.onDestroy()
    }
}
''')

# Avoid shipping a hard-coded key as if it were standards-compliant SRTP.
rtp = base / "rtp/RtpAudioEngine.kt"
rt = rtp.read_text()
rt = rt.replace("fun startAudio(remoteIp: String, remoteRtpPort: Int, codecPt: Int, enableSrtp: Boolean = true)",
                "fun startAudio(remoteIp: String, remoteRtpPort: Int, codecPt: Int, enableSrtp: Boolean = false)")
rt = rt.replace("var jitterMs = 1.8f", "var jitterMs = 0.0f")
rt = rt.replace("var packetLossPct = 0.0f", "var packetLossPct = 0.0f")
rtp.write_text(rt)

# Expose current media state to the in-call status screen.
rtp = base / "rtp/RtpAudioEngine.kt"
rt = rtp.read_text()
rt = rt.replace("private var isStreaming = false", "var isStreaming: Boolean = false\n        private set")
rtp.write_text(rt)

# Fix live VoIP effect routing by matching the RTP socket to the port in SDP.
sip = base / "sip/SipClient.kt"
s = sip.read_text()
s = s.replace('    private var currentCallId = ""', '    private var currentCallId = ""\n    @Volatile private var currentRtpPort = 0')
s = s.replace('        val rtpPort = 10000 + (100..9000).random()\n        val inviteReq', '        val rtpPort = 20000 + (0..20000).random()\n        currentRtpPort = rtpPort\n        val inviteReq')
s = s.replace('useTls = SipDebugManager.useTls, useSrtp = SipDebugManager.useSrtp', 'useTls = SipDebugManager.useTls, useSrtp = false')
s = s.replace('''                // Start Encrypted SRTP / RTP Media Audio Stream
                RtpAudioEngine.startAudio(sipServer, 10002, SipDebugManager.selectedCodecPayloadType, SipDebugManager.useSrtp)
                handler.post { onCallConnected?.invoke() }''', '''                val sdp = msg.substringAfter("\\r\\n\\r\\n", "")
                val remoteIp = Regex("(?m)^c=IN IP4 ([^\\s\\r]+)").find(sdp)?.groupValues?.get(1) ?: sipServer
                val remotePort = Regex("(?m)^m=audio (\\d+) ").find(sdp)?.groupValues?.get(1)?.toIntOrNull()
                if (remotePort == null || currentRtpPort == 0) {
                    notifyStatus("Call answered, but no usable RTP endpoint was found in SDP.")
                } else {
                    RtpAudioEngine.startAudio(remoteIp, remotePort, currentRtpPort, SipDebugManager.selectedCodecPayloadType, false)
                    notifyStatus("VoIP media starting; the selected voice effect is applied to outgoing audio.")
                }
                handler.post { onCallConnected?.invoke() }''')
s = s.replace('''    private fun getLocalIpAddress(): String {
        return "127.0.0.1"
    }''', '''    private fun getLocalIpAddress(): String {
        try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val network = interfaces.nextElement()
                if (!network.isUp || network.isLoopback) continue
                val addresses = network.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()
                    if (!address.isLoopbackAddress && address is java.net.Inet4Address) return address.hostAddress ?: continue
                }
            }
        } catch (e: Exception) { Log.w("SipClient", "IPv4 discovery failed", e) }
        return "0.0.0.0"
    }''')
sip.write_text(s)

rtp = base / "rtp/RtpAudioEngine.kt"
r = rtp.read_text()
r = r.replace('fun startAudio(remoteIp: String, remoteRtpPort: Int, codecPt: Int, enableSrtp: Boolean = true)', 'fun startAudio(remoteIp: String, remoteRtpPort: Int, localRtpPort: Int, codecPt: Int, enableSrtp: Boolean = false)')
r = r.replace('rtpSocket = DatagramSocket(10000)', 'rtpSocket = DatagramSocket(localRtpPort)')
r = r.replace('''        if (isStreaming) return
        isStreaming = true
        isEncryptedSrtp = enableSrtp''', '''        if (isStreaming) stopAudio()
        if (enableSrtp) {
            Log.e("RtpAudioEngine", "SRTP is not implemented safely; refusing fake-key encryption")
            return
        }
        isStreaming = true
        isEncryptedSrtp = false''')
r = r.replace('''        isStreaming = false
        rtpSocket?.close()''', '''        isStreaming = false
        isEncryptedSrtp = false
        rtpSocket?.close()''')
rtp.write_text(r)

# Normalize generated SDP parsing without fragile Kotlin regex escape sequences.
sip = base / "sip/SipClient.kt"
lines = sip.read_text().splitlines()
fixed = []
for line in lines:
    if 'val remoteIp = Regex(' in line:
        fixed.append('                val remoteIp = sdp.lineSequence().firstOrNull { it.startsWith("c=IN IP4 ") }?.substringAfter("c=IN IP4 ")?.trim() ?: sipServer')
    elif 'val remotePort = Regex(' in line:
        fixed.append('                val remotePort = sdp.lineSequence().firstOrNull { it.startsWith("m=audio ") }?.split(" ")?.getOrNull(1)?.toIntOrNull()')
    else:
        fixed.append(line)
sip.write_text("\n".join(fixed) + "\n")

rtp = base / "rtp/RtpAudioEngine.kt"
r = rtp.read_text()
r = r.replace('fun startAudio(remoteIp: String, remoteRtpPort: Int, codecPt: Int, enableSrtp: Boolean = false)', 'fun startAudio(remoteIp: String, remoteRtpPort: Int, localRtpPort: Int, codecPt: Int, enableSrtp: Boolean = false)')
r = r.replace('rtpSocket = DatagramSocket(10000)', 'rtpSocket = DatagramSocket(localRtpPort)')
r = r.replace('''        if (isStreaming) return
        isStreaming = true
        isEncryptedSrtp = enableSrtp''', '''        if (isStreaming) stopAudio()
        if (enableSrtp) {
            Log.e("RtpAudioEngine", "SRTP is not implemented safely; refusing fake-key encryption")
            return
        }
        isStreaming = true
        isEncryptedSrtp = false''')
r = r.replace('''        isStreaming = false
        rtpSocket?.close()''', '''        isStreaming = false
        isEncryptedSrtp = false
        rtpSocket?.close()''')
rtp.write_text(r)

# Add the receive/playback half of RTP so the user can hear the other caller too.
rtp = base / "rtp/RtpAudioEngine.kt"
r = rtp.read_text()
if 'import android.media.AudioManager' not in r:
    r = r.replace('import android.media.AudioFormat', 'import android.media.AudioFormat\nimport android.media.AudioManager')
r = r.replace('''                audioRecord.startRecording()

                val pcmBuffer = ShortArray(160)''', '''                audioRecord.startRecording()
                val minTrackSize = AudioTrack.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
                val audioTrack = AudioTrack(AudioManager.STREAM_VOICE_CALL, SAMPLE_RATE,
                    AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(minTrackSize, 160 * 4), AudioTrack.MODE_STREAM)
                audioTrack.play()

                val pcmBuffer = ShortArray(160)''')
r = r.replace('''                var timestamp = 0L

                val cipher''', '''                var timestamp = 0L

                // Receive the remote caller's RTP packets on the same negotiated socket.
                thread(name = "RTP-Receive") {
                    val incoming = ByteArray(2048)
                    while (isStreaming) {
                        try {
                            val packet = DatagramPacket(incoming, incoming.size)
                            rtpSocket?.receive(packet) ?: break
                            if (packet.length <= 12 || (packet.data[0].toInt() and 0xC0) != 0x80) continue
                            val headerLength = 12 + (packet.data[0].toInt() and 0x0F) * 4
                            if (packet.length <= headerLength) continue
                            val payloadType = packet.data[1].toInt() and 0x7F
                            if (payloadType != 0 && payloadType != 8) continue
                            val count = packet.length - headerLength
                            val decoded = ShortArray(count)
                            for (i in 0 until count) {
                                val value = packet.data[headerLength + i].toInt() and 0xFF
                                decoded[i] = if (payloadType == 0) ulawToLinear(value) else alawToLinear(value)
                            }
                            audioTrack.write(decoded, 0, decoded.size)
                        } catch (e: Exception) {
                            if (isStreaming) Log.w("RtpAudioEngine", "RTP receive ended: " + e.message)
                            break
                        }
                    }
                }

                val cipher''')
r = r.replace('''                audioRecord.stop()
                audioRecord.release()''', '''                audioRecord.stop()
                audioRecord.release()
                try { audioTrack.stop() } catch (_: Exception) {}
                audioTrack.release()''')
insert = '''
    private fun ulawToLinear(value: Int): Short {
        val u = value.inv() and 0xFF
        var sample = ((u and 0x0F) shl 3) + 0x84
        sample = sample shl ((u and 0x70) shr 4)
        val decoded = if ((u and 0x80) != 0) 0x84 - sample else sample - 0x84
        return decoded.coerceIn(-32768, 32767).toShort()
    }

    private fun alawToLinear(value: Int): Short {
        val a = value xor 0x55
        var sample = (a and 0x0F) shl 4
        val segment = (a and 0x70) shr 4
        sample += if (segment == 0) 8 else 0x108
        if (segment > 1) sample = sample shl (segment - 1)
        val decoded = if ((a and 0x80) != 0) sample else -sample
        return decoded.coerceIn(-32768, 32767).toShort()
    }

'''
if 'private fun ulawToLinear' not in r:
    r = r.replace('    private fun linearToUlaw(pcm: Int): Byte {', insert + '    private fun linearToUlaw(pcm: Int): Byte {')
rtp.write_text(r)


# Final guard: fail the APK build if the SIP/RTP voice-effects path is missing.
sip_final = (base / "sip/SipClient.kt").read_text()
rtp_final = (base / "rtp/RtpAudioEngine.kt").read_text()
voice_final = (base / "VoiceChanger.kt").read_text()
required_media_markers = {
    "SIP negotiated local RTP port": "currentRtpPort",
    "SIP starts RTP with negotiated endpoints": "startAudio(remoteIp, remotePort, currentRtpPort",
    "outgoing microphone passes through voice effect": "VoiceChanger.processPcm",
    "incoming RTP receive path": "RTP-Receive",
    "G.711 mu-law receive decoder": "ulawToLinear",
    "G.711 A-law receive decoder": "alawToLinear",
    "voice effect modes": "ANONYMIZER",
}
combined_media_source = sip_final + "\\n" + rtp_final + "\\n" + voice_final
missing_media = [label for label, marker in required_media_markers.items() if marker not in combined_media_source]
if missing_media:
    raise SystemExit("VoIP voice changer integration check failed: " + ", ".join(missing_media))
print("Validated SIP/RTP voice-effects integration markers.")

# Build the device-management and developer pathways inside this degoogled APK.
# These are app-owned screens; never bounce users into a stock dialer or vendor utility.
pathways = base / "SystemPathwaysActivity.kt"
pathways.write_text(r"""package org.degoogled.dialer

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.os.Bundle
import android.provider.Settings
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class SystemPathwaysActivity : AppCompatActivity() {
    private lateinit var body: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val scroll = ScrollView(this)
        body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(36, 28, 36, 36)
        }
        scroll.addView(body)
        setContentView(scroll)

        addText("De-Googled Device Pathways", 24f, true)
        addText("These controls and diagnostics are part of this APK. Android keeps protected device controls under operating-system enforcement.", 15f)
        addButton("Return to this APK's dialer") { finish() }

        addSection("Phone / dialer")
        addText("The dial pad, SIP calling, carrier-call request flow, in-call controls, and voice-effect controls are implemented in this APK. No stock dialer is launched from this pathway.", 15f)
        addButton("Open this APK's radio/network diagnostics") {
            startActivity(android.content.Intent(this, RadioDiagnosticsActivity::class.java))
        }

        addSection("Device administrator / enterprise")
        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val admins = try { dpm.activeAdmins?.joinToString("\\n") { it.flattenToShortString() } ?: "No active administrators reported" }
            catch (_: Exception) { "Android restricted the administrator list" }
        addText("Active administrator components reported by Android:\\n" + admins, 14f)
        addText("This APK does not silently grant itself administrator or device-owner privileges. Those privileges require an explicitly declared admin receiver and user/management approval; this screen reports what Android exposes instead of pretending the privilege was granted.", 14f)

        addSection("Developer / debugging status")
        val devEnabled = readGlobal(Settings.Global.DEVELOPMENT_SETTINGS_ENABLED)
        val adbEnabled = readGlobal(Settings.Global.ADB_ENABLED)
        val oemUnlock = readGlobal(Settings.Global.OEM_UNLOCK_ENABLED)
        addText("Developer options: " + status(devEnabled) + "\\nUSB debugging setting: " + status(adbEnabled) + "\\nOEM unlock setting: " + status(oemUnlock), 15f)
        addText("These are read-only status checks. An ordinary app cannot turn on USB debugging, bypass device policy, unlock the bootloader, or generate privileged bug reports by itself.", 14f)
        addButton("Refresh Android-reported status") { recreate() }
    }

    private fun readGlobal(key: String): Int? = try {
        Settings.Global.getInt(contentResolver, key)
    } catch (_: Exception) { null }

    private fun status(value: Int?): String = when (value) {
        1 -> "Enabled"
        0 -> "Disabled"
        else -> "Unavailable / restricted"
    }

    private fun addSection(text: String) {
        addText(text, 19f, true)
    }

    private fun addText(text: String, size: Float, bold: Boolean = false) {
        body.addView(TextView(this).apply {
            this.text = text
            textSize = size
            if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(0, 10, 0, 10)
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }

    private fun addButton(text: String, action: () -> Unit) {
        body.addView(Button(this).apply {
            this.text = text
            setOnClickListener { action() }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }
}
""")

# Replace the previous external-app shortcuts with one in-app pathway entry.
main_text = main.read_text()
old = """        // Native system tools: these open Android-owned screens; they do not silently enable admin rights.
        val systemTools = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(12, 8, 12, 8)
        }
        fun addSystemTool(label: String, action: () -> Unit) {
            val button = Button(this).apply {
                text = label
                setOnClickListener { action() }
            }
            systemTools.addView(button, android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ))
        }
        addSystemTool("Open Phone / Dialer") {
            try {
                startActivity(Intent(Intent.ACTION_DIAL))
            } catch (_: Exception) {
                Toast.makeText(this, "No dialer app is available.", Toast.LENGTH_LONG).show()
            }
        }
        addSystemTool("Device Admin / Enterprise Settings") {
            try {
                startActivity(Intent("android.settings.DEVICE_ADMIN_SETTINGS"))
            } catch (_: Exception) {
                try { startActivity(Intent(android.provider.Settings.ACTION_SECURITY_SETTINGS)) }
                catch (_: Exception) {
                    Toast.makeText(this, "Device administration settings are unavailable on this device.", Toast.LENGTH_LONG).show()
                }
            }
        }
        addSystemTool("Native Android Developer Options") {
            try {
                startActivity(Intent(android.provider.Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS))
            } catch (_: Exception) {
                Toast.makeText(this, "Developer Options is unavailable or restricted by device policy.", Toast.LENGTH_LONG).show()
            }
        }
        val contentRoot = findViewById<android.view.ViewGroup>(android.R.id.content)
        contentRoot.addView(systemTools)
"""
new = """        // In-app pathways: do not delegate the phone UI to a preinstalled dialer or vendor app.
        val pathwaysButton = Button(this).apply {
            text = "Device Admin / Developer Pathways"
            setOnClickListener { startActivity(Intent(this@MainActivity, SystemPathwaysActivity::class.java)) }
        }
        findViewById<android.view.ViewGroup>(android.R.id.content).addView(pathwaysButton)
"""
if (!main_text.includes(old)) throw new Error("Could not locate old external-app shortcut block in generated MainActivity");
main.write_text(main_text.replace(old, new, 1));

# Register the app-owned pathway screen in AndroidManifest.xml.
m = manifest.read_text()
activity = '        <activity android:name=".SystemPathwaysActivity" android:exported="false" />'
if (!m.includes('android:name=".SystemPathwaysActivity"')) {
  const anchor = '        <application'
  const appIdx = m.indexOf(anchor)
  if (appIdx < 0) throw new Error("Could not find manifest application element")
  // Insert after the application opening tag so this remains an app-owned, non-exported activity.
  const end = m.indexOf('>', appIdx)
  m = m.slice(0, end + 1) + "\n" + activity + m.slice(end + 1)
  manifest.write_text(m)
}
print("Added app-owned Device Admin / Developer Pathways screen; removed stock dialer and settings-app shortcuts.")
