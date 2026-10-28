from pathlib import Path
import sys, re

root = Path(sys.argv[1])
base = root / "app/src/main/java/org/degoogled/dialer"
manifest = root / "app/src/main/AndroidManifest.xml"
main = base / "MainActivity.kt"
svc = base / "CustomInCallService.kt"
rtp = base / "rtp/RtpAudioEngine.kt"
sip = base / "sip/SipClient.kt"
if not all(p.exists() for p in (manifest, main, svc, rtp, sip)):
    raise SystemExit("Call feature patch: unexpected source layout")

svc.write_text(r'''package org.degoogled.dialer
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log

class CustomInCallService : InCallService() {
    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= 26) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL, "Phone calls", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Incoming and ongoing call controls"
                    lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                })
        }
    }
    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        activeCall = call
        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                if (state == Call.STATE_DISCONNECTED) {
                    clearNotification()
                    if (activeCall === call) activeCall = null
                } else showNotification(call, state)
            }
            override fun onDetailsChanged(call: Call, details: Call.Details) = showNotification(call, call.state)
        })
        showNotification(call, call.state)
    }
    override fun onCallRemoved(call: Call) {
        if (activeCall === call) activeCall = null
        clearNotification()
        super.onCallRemoved(call)
    }
    private fun showNotification(call: Call, state: Int) {
        val handle = call.details.handle?.schemeSpecificPart ?: "Unknown number"
        val incoming = state == Call.STATE_RINGING
        val person = android.app.Person.Builder().setName(handle).build()
        val builder = if (Build.VERSION.SDK_INT >= 31) {
            Notification.Builder(this, CHANNEL).setStyle(
                if (incoming) Notification.CallStyle.forIncomingCall(person, action(ACTION_ANSWER), action(ACTION_REJECT))
                else Notification.CallStyle.forOngoingCall(person, action(ACTION_HANGUP)))
        } else {
            Notification.Builder(this).setContentTitle(if (incoming) "Incoming call" else "Call in progress")
                .setContentText(handle)
                .addAction(0, if (incoming) "Answer" else "Hang up", action(if (incoming) ACTION_ANSWER else ACTION_HANGUP))
                .apply { if (incoming) addAction(0, "Decline", action(ACTION_REJECT)) }
        }
        builder.setSmallIcon(android.R.drawable.sym_action_call)
            .setCategory(Notification.CATEGORY_CALL).setOngoing(incoming || state == Call.STATE_ACTIVE)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIFICATION_ID, builder.build())
    }
    private fun action(name: String): PendingIntent = PendingIntent.getBroadcast(
        this, name.hashCode(), Intent(this, CallActionReceiver::class.java).setAction(name),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    private fun clearNotification() {
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIFICATION_ID)
    }
    companion object {
        private const val CHANNEL = "dialer_calls"
        private const val NOTIFICATION_ID = 4401
        const val ACTION_ANSWER = "org.degoogled.dialer.ANSWER_CALL"
        const val ACTION_REJECT = "org.degoogled.dialer.REJECT_CALL"
        const val ACTION_HANGUP = "org.degoogled.dialer.HANGUP_CALL"
        @Volatile var activeCall: Call? = null
            private set
        fun answer() { activeCall?.answer(android.telecom.VideoProfile.STATE_AUDIO_ONLY) }
        fun reject() { activeCall?.reject(false, null) }
        fun hangup() { activeCall?.disconnect() }
    }
}
''')

(base / "CallActionReceiver.kt").write_text(r'''package org.degoogled.dialer
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
class CallActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        when (intent?.action) {
            CustomInCallService.ACTION_ANSWER -> CustomInCallService.answer()
            CustomInCallService.ACTION_REJECT -> CustomInCallService.reject()
            CustomInCallService.ACTION_HANGUP -> CustomInCallService.hangup()
            else -> Toast.makeText(context, "Unsupported call action.", Toast.LENGTH_SHORT).show()
        }
    }
}
''')

s = main.read_text()
if "requestDefaultDialerRole" not in s:
    s = s.replace("import android.content.Intent\n", "import android.content.Intent\nimport android.app.role.RoleManager\nimport android.telecom.TelecomManager\nimport android.view.ViewGroup\n", 1)
    s = s.replace("        setContentView(R.layout.activity_main)\n", """        setContentView(R.layout.activity_main)
        val roleButton = Button(this).apply {
            text = "Set as default phone app"
            setOnClickListener { requestDefaultDialerRole() }
        }
        (findViewById<ViewGroup>(android.R.id.content).getChildAt(0) as? ViewGroup)?.addView(roleButton, 0)
""", 1)
    method = """    private fun requestDefaultDialerRole() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 29) {
                val roles = getSystemService(RoleManager::class.java)
                when {
                    roles.isRoleHeld(RoleManager.ROLE_DIALER) ->
                        Toast.makeText(this, "Already selected as the default phone app.", Toast.LENGTH_LONG).show()
                    roles.isRoleAvailable(RoleManager.ROLE_DIALER) ->
                        startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_DIALER), 704)
                    else -> Toast.makeText(this, "Android does not expose the dialer role on this device.", Toast.LENGTH_LONG).show()
                }
            } else {
                @Suppress("DEPRECATION")
                startActivityForResult(Intent(TelecomManager.ACTION_CHANGE_DEFAULT_DIALER)
                    .putExtra(TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, packageName), 704)
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Could not open Android's default-phone-app chooser: ${e.message ?: e.javaClass.simpleName}", Toast.LENGTH_LONG).show()
        }
    }

"""
    s = s.replace("    override fun onNewIntent(intent: Intent) {", method + "    override fun onNewIntent(intent: Intent) {", 1)
    # Normalize imports after patching, avoiding duplicate Kotlin imports on rebuilds.
    main.write_text('\n'.join(dict.fromkeys(s.splitlines())) + '\n')
m = manifest.read_text()
if "CallActionReceiver" not in m:
    m = m.replace("        <!-- Native AOSP Telecom InCallService -->", '        <receiver android:name=".CallActionReceiver" android:exported="false" />\n\n        <!-- Native AOSP Telecom InCallService -->')
if 'android.telecom.IN_CALL_SERVICE_UI' not in m:
    m = m.replace('<action android:name="android.telecom.InCallService" />', '<action android:name="android.telecom.InCallService" />\n            </intent-filter>\n            <meta-data android:name="android.telecom.IN_CALL_SERVICE_UI" android:value="true" />\n            <meta-data android:name="android.telecom.IN_CALL_SERVICE_RINGING" android:value="true" />\n            <intent-filter>\n                <action android:name="android.telecom.InCallService" />')
manifest.write_text(m)

# Bidirectional RTP: use actual negotiated SDP endpoint and play decoded G.711 received packets.
s = rtp.read_text()
s = s.replace('import android.media.AudioRecord\n', 'import android.media.AudioRecord\nimport android.media.AudioTrack\nimport android.media.AudioManager\nimport java.net.InetSocketAddress\n')
s = s.replace('rtpSocket = DatagramSocket(10000)', 'rtpSocket = DatagramSocket(null).apply { reuseAddress = true; bind(InetSocketAddress(10000)) }')
needle = '                audioRecord.startRecording()\n'
receive = '''
                // Receive remote RTP on the same bound socket and play decoded G.711 audio.
                val trackMin = AudioTrack.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
                val audioTrack = AudioTrack(AudioManager.STREAM_VOICE_CALL, SAMPLE_RATE,
                    AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(trackMin, 3200), AudioTrack.MODE_STREAM)
                audioTrack.play()
                val receiveSocket = rtpSocket
                thread(name = "RTP-receive") {
                    val incoming = ByteArray(2048)
                    while (isStreaming && receiveSocket != null && !receiveSocket.isClosed) {
                        try {
                            val datagram = DatagramPacket(incoming, incoming.size)
                            receiveSocket.receive(datagram)
                            if (datagram.length <= 12) continue
                            val offset = 12 + ((datagram.data[0].toInt() and 0x0F) * 4)
                            if (offset >= datagram.length) continue
                            val count = datagram.length - offset
                            val pcm = ShortArray(count)
                            val pt = datagram.data[1].toInt() and 0x7F
                            for (i in 0 until count) {
                                val b = datagram.data[offset + i].toInt() and 0xFF
                                pcm[i] = if (pt == 8) alawToLinear(b) else ulawToLinear(b)
                            }
                            audioTrack.write(pcm, 0, pcm.size)
                        } catch (e: Exception) {
                            if (isStreaming) Log.w("RtpAudioEngine", "RTP receive ended: ${e.message}")
                        }
                    }
                    try { audioTrack.stop() } catch (_: Exception) {}
                    audioTrack.release()
                }
'''
s = s.replace(needle, needle + receive, 1)
s = s.replace('''    fun stopAudio() {
        isStreaming = false''', '''    fun stopAudio() {
        isStreaming = false''')
# Append G.711 decoders before linearToUlaw
dec = '''
    private fun ulawToLinear(value: Int): Short {
        val u = value.inv() and 0xFF
        val t = (((u and 0x0F) shl 3) + 0x84) shl ((u and 0x70) shr 4)
        return (if ((u and 0x80) != 0) 0x84 - t else t - 0x84).toShort()
    }
    private fun alawToLinear(value: Int): Short {
        val a = value xor 0x55
        var t = (a and 0x0F) shl 4
        val seg = (a and 0x70) shr 4
        t += if (seg == 0) 8 else if (seg == 1) 0x108 else (0x108 shl (seg - 1))
        return (if ((a and 0x80) != 0) t else -t).toShort()
    }

'''
if 'private fun ulawToLinear' not in s:
    s = s.replace('    private fun linearToUlaw(pcm: Int): Byte {', dec + '    private fun linearToUlaw(pcm: Int): Byte {')
# Do not pretend homemade fixed-key CTR is SRTP; refuse this unsafe mode.
s = s.replace('''        isStreaming = true
        isEncryptedSrtp = enableSrtp''', '''        if (enableSrtp) {
            Log.e("RtpAudioEngine", "SRTP is unsupported: no negotiated key exchange/authentication is implemented.")
            return
        }
        isStreaming = true
        isEncryptedSrtp = false''')
s = s.replace('''                        val finalPayload = if (enableSrtp) {''', '''                        val finalPayload = if (false) {''')
rtp.write_text('\\n'.join(dict.fromkeys(s.splitlines()) ) + '\\n')

# Parse remote media endpoint from the 200 OK SDP instead of assuming a fixed server port.
s = sip.read_text()
s = s.replace('''                RtpAudioEngine.startAudio(sipServer, 10002, SipDebugManager.selectedCodecPayloadType, SipDebugManager.useSrtp)''', '''                val mediaIp = Regex("(?m)^c=IN IP4 ([^\\\\r\\\\n]+)").find(msg)?.groupValues?.get(1)?.trim() ?: sipServer
                val mediaPort = Regex("(?m)^m=audio (\\\\d+)").find(msg)?.groupValues?.get(1)?.toIntOrNull()
                if (mediaPort != null && mediaPort in 1..65535) {
                    RtpAudioEngine.startAudio(mediaIp, mediaPort, SipDebugManager.selectedCodecPayloadType, SipDebugManager.useSrtp)
                } else {
                    notifyStatus("SIP connected but remote audio port was not negotiated; audio unavailable.")
                }''')
# Correct local IP selection; no loopback address in SDP.
s = s.replace('''    private fun getLocalIpAddress(): String {
        return "127.0.0.1"
    }''', '''    private fun getLocalIpAddress(): String {
        return try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (!iface.isUp || iface.isLoopback) continue
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()
                    if (address is java.net.Inet4Address && !address.isLoopbackAddress && !address.isLinkLocalAddress)
                        return address.hostAddress ?: "0.0.0.0"
                }
            }
            "0.0.0.0"
        } catch (_: Exception) { "0.0.0.0" }
    }''')
sip.write_text(s)
print("Applied Telecom answer/reject/hangup notifications, default dialer chooser, negotiated RTP receive/playback, and explicit SRTP unsupported behavior.")
