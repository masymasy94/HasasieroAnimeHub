package com.hasasiero.tvstream.data.remote

import android.content.Context
import android.os.Build
import android.util.Log
import com.hasasiero.tvstream.BuildConfig
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Logs to logcat AND to the server (POST /api/client-log → `docker logs animehub`),
 * so TV problems are visible without adb. A crash is written to disk first and
 * re-sent on the next start if the upload didn't make it before the process died.
 */
object RemoteLog {
    private const val TAG = "AnimeHub"
    private val JSON = "application/json".toMediaType()

    // Own client: going through the app's client would log the log upload itself.
    private val http = OkHttpClient.Builder().callTimeout(5, TimeUnit.SECONDS).build()
    private var baseUrl: () -> String = { BuildConfig.DEFAULT_SERVER_URL }
    private var crashFile: File? = null

    fun init(context: Context, baseUrl: () -> String) {
        this.baseUrl = baseUrl
        crashFile = File(context.filesDir, "pending_crash.json")

        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, t -> onCrash(thread, t); previous?.uncaughtException(thread, t) }

        i("App", "start v${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) " +
            "${Build.MANUFACTURER} ${Build.MODEL} Android ${Build.VERSION.RELEASE} (sdk ${Build.VERSION.SDK_INT}) " +
            "server=${baseUrl()}")

        crashFile?.takeIf { it.exists() }?.let { file ->
            post(JSONArray(file.readText()), onSent = { file.delete() })
        }
    }

    fun d(tag: String, msg: String) = log("D", tag, msg, null)
    fun i(tag: String, msg: String) = log("I", tag, msg, null)
    fun w(tag: String, msg: String, t: Throwable? = null) = log("W", tag, msg, t)
    fun e(tag: String, msg: String, t: Throwable? = null) = log("E", tag, msg, t)

    private fun log(level: String, tag: String, msg: String, t: Throwable?) {
        val full = if (t != null) "$msg\n${Log.getStackTraceString(t)}" else msg
        Log.println(if (level == "E") Log.ERROR else if (level == "W") Log.WARN else Log.INFO, "$TAG/$tag", full)
        post(JSONArray().put(entry(level, tag, full)))
    }

    private fun entry(level: String, tag: String, msg: String) = JSONObject()
        .put("level", level).put("tag", tag).put("message", msg)
        .put("ts", SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date()))

    private fun request(entries: JSONArray) = Request.Builder()
        .url("${baseUrl().trimEnd('/')}/api/client-log")
        .post(entries.toString().toRequestBody(JSON))
        .build()

    private fun post(entries: JSONArray, onSent: () -> Unit = {}) {
        try {
            http.newCall(request(entries)).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {}
                override fun onResponse(call: Call, response: Response) {
                    response.close()
                    if (response.isSuccessful) onSent()
                }
            })
        } catch (_: Exception) {} // bad server URL: logcat still has it
    }

    private fun onCrash(thread: Thread, t: Throwable) {
        val entries = JSONArray()
            .put(entry("E", "Crash", "UNCAUGHT EXCEPTION on thread ${thread.name}\n${Log.getStackTraceString(t)}"))
            .put(entry("E", "Crash", "last logcat lines:\n${recentLogcat()}"))
        Log.e(TAG, "UNCAUGHT EXCEPTION", t)
        try { crashFile?.writeText(entries.toString()) } catch (_: Exception) {}

        // Network is not allowed on the main thread, and the process dies right
        // after this handler: upload from a helper thread, wait a bit for it.
        val upload = Thread {
            try {
                http.newCall(request(entries)).execute().use { if (it.isSuccessful) crashFile?.delete() }
            } catch (_: Exception) {}
        }
        upload.start()
        upload.join(3000)
    }

    // Without READ_LOGS an app only sees its own process's lines — exactly what we want.
    private fun recentLogcat(): String = try {
        Runtime.getRuntime().exec(arrayOf("logcat", "-d", "-t", "300", "-v", "time"))
            .inputStream.bufferedReader().readText()
    } catch (e: Exception) {
        "logcat unavailable: $e"
    }
}
