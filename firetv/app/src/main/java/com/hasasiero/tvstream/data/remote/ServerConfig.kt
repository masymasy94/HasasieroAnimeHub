package com.hasasiero.tvstream.data.remote

import android.content.Context
import android.content.SharedPreferences
import com.hasasiero.tvstream.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ServerConfig @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("server_config", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString("base_url", BuildConfig.DEFAULT_SERVER_URL)
            ?: BuildConfig.DEFAULT_SERVER_URL
        set(value) = prefs.edit().putString("base_url", value.trimEnd('/')).apply()
}
