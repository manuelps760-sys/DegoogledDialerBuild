package org.degoogled.dialer.flutter

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telecom.Call
import android.telecom.InCallService

class DialerInCallService : InCallService() {
    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= 26) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL, "Call controls", NotificationManager.IMPORTANCE_HIGH))
        }
    }
    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        currentCall = call
        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                if (state == Call.STATE_DISCONNECTED) {
                    getSystemService(NotificationManager::class.java).cancel(ID)
                    if (currentCall === call) currentCall = null
                } else notifyCall(call, state)
            }
        })
        notifyCall(call, call.state)
    }
    override fun onCallRemoved(call: Call) {
        if (currentCall === call) currentCall = null
        getSystemService(NotificationManager::class.java).cancel(ID)
        super.onCallRemoved(call)
    }
    private fun notifyCall(call: Call, state: Int) {
        val incoming = state == Call.STATE_RINGING
        val number = call.details.handle?.schemeSpecificPart ?: "Phone call"
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL) else Notification.Builder(this)
        builder.setSmallIcon(android.R.drawable.sym_action_call)
            .setContentTitle(if (incoming) "Incoming call" else "Call in progress")
            .setContentText(number)
            .setCategory(Notification.CATEGORY_CALL)
            .setOngoing(incoming || state == Call.STATE_ACTIVE)
        if (incoming) {
            builder.addAction(0, "Answer", action(ACTION_ANSWER))
            builder.addAction(0, "Decline", action(ACTION_REJECT))
        } else {
            builder.addAction(0, "Hang up", action(ACTION_HANGUP))
        }
        getSystemService(NotificationManager::class.java).notify(ID, builder.build())
    }
    private fun action(name: String): PendingIntent = PendingIntent.getBroadcast(
        this, name.hashCode(), Intent(this, CallActionReceiver::class.java).setAction(name),
        PendingIntent.FLAG_UPDATE_CURRENT or if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0)
    companion object {
        private const val CHANNEL = "degoogled_calls"
        private const val ID = 5512
        const val ACTION_ANSWER = "org.degoogled.dialer.flutter.ANSWER"
        const val ACTION_REJECT = "org.degoogled.dialer.flutter.REJECT"
        const val ACTION_HANGUP = "org.degoogled.dialer.flutter.HANGUP"
        @Volatile var currentCall: Call? = null
            private set
    }
}
class CallActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        when (intent?.action) {
            DialerInCallService.ACTION_ANSWER -> DialerInCallService.currentCall?.answer(android.telecom.VideoProfile.STATE_AUDIO_ONLY)
            DialerInCallService.ACTION_REJECT -> DialerInCallService.currentCall?.reject(false, null)
            DialerInCallService.ACTION_HANGUP -> DialerInCallService.currentCall?.disconnect()
        }
    }
}
