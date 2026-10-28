package org.degoogled.dialer.flutter

import android.app.role.RoleManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channel = "org.degoogled.dialer/phone"
    private var pendingRoleResult: MethodChannel.Result? = null
    private val accountHandles = mutableMapOf<String, PhoneAccountHandle>()

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            when (call.method) {
                "isDefaultDialer" -> result.success(isDefaultDialer())
                "requestDefaultDialer" -> {
                    try {
                        if (isDefaultDialer()) {
                            result.success(true)
                        } else if (Build.VERSION.SDK_INT >= 29) {
                            val roles = getSystemService(RoleManager::class.java)
                            if (!roles.isRoleAvailable(RoleManager.ROLE_DIALER)) {
                                result.error("ROLE_UNAVAILABLE", "Android dialer role unavailable", null)
                            } else {
                                pendingRoleResult = result
                                startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_DIALER), ROLE_REQUEST)
                            }
                        } else {
                            @Suppress("DEPRECATION")
                            startActivity(Intent(TelecomManager.ACTION_CHANGE_DEFAULT_DIALER)
                                .putExtra(TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, packageName))
                            result.success(false)
                        }
                    } catch (e: Exception) {
                        pendingRoleResult = null
                        result.error("ROLE_REQUEST_FAILED", e.message, null)
                    }
                }
                "getPhoneAccounts" -> {
                    try {
                        val telecom = getSystemService(TelecomManager::class.java)
                        accountHandles.clear()
                        val accounts = telecom.callCapablePhoneAccounts.orEmpty().mapIndexed { index, handle ->
                            val id = "account_$index"
                            accountHandles[id] = handle
                            val account = telecom.getPhoneAccount(handle)
                            mapOf(
                                "id" to id,
                                "label" to (account?.label?.toString() ?: "SIM ${index + 1}"),
                                "address" to (account?.address?.schemeSpecificPart ?: ""),
                                "subscription" to (account?.subscriptionAddress?.schemeSpecificPart ?: "")
                            )
                        }
                        result.success(accounts)
                    } catch (e: Exception) {
                        result.error("PHONE_ACCOUNTS_FAILED", e.message, null)
                    }
                }
                "placeCall" -> {
                    val dial = call.argument<String>("number")?.trim().orEmpty()
                    val accountId = call.argument<String>("accountId")
                    if (dial.isBlank()) result.error("EMPTY_NUMBER", "Enter a phone number", null)
                    else {
                        try {
                            if (isDefaultDialer() && Build.VERSION.SDK_INT >= 23) {
                                val telecom = getSystemService(TelecomManager::class.java)
                                val extras = android.os.Bundle()
                                accountId?.let { accountHandles[it] }?.let {
                                    extras.putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, it)
                                }
                                telecom.placeCall(Uri.fromParts("tel", dial, null), extras)
                                result.success(true)
                            } else {
                                startActivity(Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", dial, null)))
                                result.success(false)
                            }
                        } catch (e: SecurityException) {
                            result.error("CALL_PERMISSION", "Android denied the call request. Use the system dialer or check permissions.", null)
                        } catch (e: Exception) {
                            result.error("CALL_FAILED", e.message, null)
                        }
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    @Deprecated("Deprecated by Android, retained for role chooser result")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ROLE_REQUEST) {
            val result = pendingRoleResult
            pendingRoleResult = null
            result?.success(isDefaultDialer())
        }
    }

    private fun isDefaultDialer(): Boolean = try {
        if (Build.VERSION.SDK_INT >= 29) {
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_DIALER)
        } else {
            @Suppress("DEPRECATION")
            getSystemService(TelecomManager::class.java).defaultDialerPackage == packageName
        }
    } catch (_: Exception) { false }

    companion object {
        private const val ROLE_REQUEST = 704
    }
}
