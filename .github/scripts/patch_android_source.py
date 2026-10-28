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

radio.write_text("""package org.degoogled.dialer

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
if "android.permission.MODIFY_AUDIO_SETTINGS" not in m:
    m = m.replace('<uses-permission android:name="android.permission.RECORD_AUDIO" />',
        '<uses-permission android:name="android.permission.RECORD_AUDIO" />\n    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />')
manifest.write_text(m)

print("Source improvements applied.")
