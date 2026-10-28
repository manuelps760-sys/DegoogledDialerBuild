package org.degoogled.dialer.flutter

import android.app.role.RoleManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.telecom.TelecomManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channel = "org.degoogled.dialer/phone"
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            when (call.method) {
                "isDefaultDialer" -> result.success(isDefaultDialer())
                "requestDefaultDialer" -> {
                    try {
                        if (Build.VERSION.SDK_INT >= 29) {
                            val roles = getSystemService(RoleManager::class.java)
                            if (!roles.isRoleAvailable(RoleManager.ROLE_DIALER)) {
                                result.error("ROLE_UNAVAILABLE", "Android dialer role unavailable", null)
                            } else if (roles.isRoleHeld(RoleManager.ROLE_DIALER)) {
                                result.success(true)
                            } else {
                                startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_DIALER), 704)
                                result.success(false)
                            }
                        } else {
                            @Suppress("DEPRECATION")
                            startActivity(Intent(TelecomManager.ACTION_CHANGE_DEFAULT_DIALER)
                                .putExtra(TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, packageName))
                            result.success(false)
                        }
                    } catch (e: Exception) { result.error("ROLE_REQUEST_FAILED", e.message, null) }
                }
                "placeCall" -> {
                    val dial = call.argument<String>("number")?.trim().orEmpty()
                    if (dial.isBlank()) result.error("EMPTY_NUMBER", "Enter a phone number", null)
                    else {
                        try {
                            if (isDefaultDialer() && Build.VERSION.SDK_INT >= 23) {
                                val telecom = getSystemService(TelecomManager::class.java)
                                telecom.placeCall(Uri.fromParts("tel", dial, null), null)
                                result.success(true)
                            } else {
                                startActivity(Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", dial, null)))
                                result.success(false)
                            }
                        } catch (e: SecurityException) { result.error("CALL_PERMISSION", "Android denied the call request. Use the system dialer or check permissions.", null) }
                        catch (e: Exception) { result.error("CALL_FAILED", e.message, null) }
                    }
                }
                else -> result.notImplemented()
            }
        }
    }
    private fun isDefaultDialer(): Boolean = try {
        if (Build.VERSION.SDK_INT >= 29) getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_DIALER)
        else getSystemService(TelecomManager::class.java).defaultDialerPackage == packageName
    } catch (_: Exception) { false }
}
