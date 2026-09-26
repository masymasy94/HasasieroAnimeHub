package com.hasasiero.tvstream

import android.app.Application
import com.hasasiero.tvstream.data.remote.RemoteLog
import com.hasasiero.tvstream.data.remote.ServerConfig
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class TvStreamApp : Application() {
    @Inject
    lateinit var serverConfig: ServerConfig

    override fun onCreate() {
        super.onCreate()
        // Crash handler + log upload to the server (see `docker logs animehub | grep animehub.tv`)
        RemoteLog.init(this) { serverConfig.baseUrl }
    }
}
