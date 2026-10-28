from pathlib import Path
import sys

root = Path(sys.argv[1])
base = root / "app/src/main/java/org/degoogled/dialer"
manifest = root / "app/src/main/AndroidManifest.xml"
main = base / "MainActivity.kt"
if not all(p.exists() for p in (base, manifest, main)):
    raise SystemExit("Dialer completion patch: unexpected Android source layout")

# App-owned contacts and recent-call browser. Selecting an entry routes back through
# Android's DIAL intent, so the user sees/controls the actual call action.
hub = base / "DialerHubActivity.kt"
hub.write_text(r'''package org.degoogled.dialer

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.CallLog
import android.provider.ContactsContract
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class DialerHubActivity : Activity() {
    private lateinit var list: LinearLayout
    private lateinit var status: TextView
    private var showingRecents = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 20, 24, 20)
        }
        page.addView(TextView(this).apply { text = "Contacts & call history"; textSize = 24f })
        status = TextView(this).apply { textSize = 14f; setPadding(0, 8, 0, 8) }
        page.addView(status)
        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        actions.addView(Button(this).apply {
            text = "Contacts"
            setOnClickListener { showingRecents = false; loadEntries() }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        actions.addView(Button(this).apply {
            text = "Recent calls"
            setOnClickListener { showingRecents = true; loadEntries() }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        page.addView(actions)
        val scroll = ScrollView(this)
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(list)
        page.addView(scroll, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        ))
        page.addView(Button(this).apply { text = "Back to dialer"; setOnClickListener { finish() } })
        setContentView(page)
        loadEntries()
    }

    private fun loadEntries() {
        list.removeAllViews()
        val permission = if (showingRecents) Manifest.permission.READ_CALL_LOG else Manifest.permission.READ_CONTACTS
        if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
            status.text = if (showingRecents)
                "Call history permission is required. Android may allow it only while this app is the default dialer."
            else "Contacts permission is required to browse saved contacts."
            requestPermissions(arrayOf(permission), if (showingRecents) 812 else 811)
            return
        }
        try {
            if (showingRecents) loadRecents() else loadContacts()
        } catch (e: SecurityException) {
            status.text = "Android denied access. Set this app as the default dialer and grant the requested permission, then retry."
        } catch (e: Exception) {
            status.text = "Could not read entries: " + (e.message ?: e.javaClass.simpleName)
        }
    }

    private fun loadContacts() {
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection, null, null,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " COLLATE NOCASE ASC"
        )?.use { cursor ->
            val nameCol = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numberCol = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            var count = 0
            while (cursor.moveToNext()) {
                val name = cursor.getString(nameCol) ?: "Unnamed contact"
                val number = cursor.getString(numberCol) ?: continue
                addEntry(name, number, "Tap to dial")
                count++
            }
            status.text = if (count == 0) "No phone numbers found in contacts." else "$count contact numbers"
        }
    }

    private fun loadRecents() {
        val projection = arrayOf(
            CallLog.Calls.CACHED_NAME, CallLog.Calls.NUMBER,
            CallLog.Calls.TYPE, CallLog.Calls.DATE
        )
        contentResolver.query(
            CallLog.Calls.CONTENT_URI, projection, null, null,
            CallLog.Calls.DATE + " DESC LIMIT 100"
        )?.use { cursor ->
            val nameCol = cursor.getColumnIndex(CallLog.Calls.CACHED_NAME)
            val numberCol = cursor.getColumnIndex(CallLog.Calls.NUMBER)
            val typeCol = cursor.getColumnIndex(CallLog.Calls.TYPE)
            val dateCol = cursor.getColumnIndex(CallLog.Calls.DATE)
            var count = 0
            while (cursor.moveToNext()) {
                val number = cursor.getString(numberCol) ?: continue
                val name = cursor.getString(nameCol)?.takeIf { it.isNotBlank() } ?: number
                val type = when (cursor.getInt(typeCol)) {
                    CallLog.Calls.INCOMING_TYPE -> "Incoming"
                    CallLog.Calls.OUTGOING_TYPE -> "Outgoing"
                    CallLog.Calls.MISSED_TYPE -> "Missed"
                    CallLog.Calls.REJECTED_TYPE -> "Rejected"
                    else -> "Call"
                }
                val whenText = java.text.DateFormat.getDateTimeInstance().format(java.util.Date(cursor.getLong(dateCol)))
                addEntry(name, number, "$type • $whenText")
                count++
            }
            status.text = if (count == 0) "No recent calls recorded." else "$count recent calls"
        }
    }

    private fun addEntry(title: String, number: String, detail: String) {
        val item = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(8, 12, 8, 12)
            addView(TextView(this@DialerHubActivity).apply { text = title; textSize = 18f })
            addView(TextView(this@DialerHubActivity).apply { text = "$number\n$detail"; textSize = 14f })
            setOnClickListener {
                try {
                    startActivity(Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", number, null)))
                } catch (_: Exception) {
                    Toast.makeText(this@DialerHubActivity, "No dialer can handle this number.", Toast.LENGTH_LONG).show()
                }
            }
        }
        list.addView(item, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ))
        val divider = android.view.View(this).apply {
            setBackgroundColor(0x33808080)
        }
        list.addView(divider, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1))
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 811 || requestCode == 812) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) loadEntries()
            else status.text = "Permission denied. You can still enter a number manually in the dial pad."
        }
    }
}
''')

m = manifest.read_text()
# Ensure permissions exist even if earlier patch behavior changes.
for permission in ("android.permission.READ_CONTACTS", "android.permission.READ_CALL_LOG"):
    tag = f'<uses-permission android:name="{permission}" />'
    if tag not in m:
        m = m.replace("</manifest>", "    " + tag + "\n</manifest>")
activity = '        <activity android:name=".DialerHubActivity" android:exported="false" />'
if 'android:name=".DialerHubActivity"' not in m:
    marker = '        <activity android:name=".SystemPathwaysActivity" android:exported="false" />'
    if marker in m:
        m = m.replace(marker, marker + "\n" + activity)
    else:
        start = m.find("<application")
        end = m.find(">", start)
        if start < 0 or end < 0:
            raise SystemExit("Cannot register DialerHubActivity: manifest application tag missing")
        m = m[:end+1] + "\n" + activity + m[end+1:]
manifest.write_text(m)

s = main.read_text()
# Add a real navigation entry inside the app's existing root layout (not a FrameLayout overlay).
needle = '        if "Device Admin / Developer Pathways" not in main_text:'
if "DialerHubActivity::class.java" not in s:
    # Existing patch script adds the developer pathways button at the end of onCreate.
    anchor = '        findViewById<Button>(R.id.btnLaunchRadioDiag).setOnClickListener {\n            startActivity(Intent(this, RadioDiagnosticsActivity::class.java))\n        }'
    if anchor not in s:
        raise SystemExit("Cannot add Contacts & History button: MainActivity diagnostics anchor not found")
    addition = anchor + '''
        val rootLayout = (findViewById<android.view.ViewGroup>(android.R.id.content)).getChildAt(0) as? android.view.ViewGroup
        rootLayout?.addView(Button(this).apply {
            text = "Contacts & Call History"
            setOnClickListener { startActivity(Intent(this@MainActivity, DialerHubActivity::class.java)) }
        }, android.view.ViewGroup.LayoutParams(
            android.view.ViewGroup.LayoutParams.MATCH_PARENT,
            android.view.ViewGroup.LayoutParams.WRAP_CONTENT
        ))'''
    s = s.replace(anchor, addition, 1)
    main.write_text(s)

# A phone-number dialer should not misroute SIP URIs into ACTION_CALL.
s = main.read_text()
old = '''            } else if (sipRegistered) {
                sipClient?.makeCall(target, SipDebugManager.selectedCodecPayloadType)
            } else {
                pendingNumber = target'''
new = '''            } else if (sipRegistered || target.startsWith("sip:", ignoreCase = true) || target.contains("@")) {
                if (sipRegistered) {
                    sipClient?.makeCall(target.removePrefix("sip:"), SipDebugManager.selectedCodecPayloadType)
                } else {
                    Toast.makeText(this, "This is a SIP address. Register your SIP account before placing this call.", Toast.LENGTH_LONG).show()
                }
            } else {
                pendingNumber = target'''
if old in s:
    s = s.replace(old, new, 1)
    main.write_text(s)

print("Added in-app Contacts & Call History, runtime permission handling, tap-to-dial, and SIP address routing.")
