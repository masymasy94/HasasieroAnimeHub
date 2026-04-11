package com.hasasiero.tvstream

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import com.hasasiero.tvstream.data.remote.ServerConfig
import com.hasasiero.tvstream.navigation.AppNavGraph
import com.hasasiero.tvstream.ui.settings.ServerSetupDialog
import com.hasasiero.tvstream.ui.theme.TvStreamTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var serverConfig: ServerConfig

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TvStreamTheme {
                var showSetup by remember { mutableStateOf(!serverConfig.isConfigured) }

                if (showSetup) {
                    ServerSetupDialog(
                        currentUrl = serverConfig.baseUrl,
                        onConfirm = { url ->
                            serverConfig.baseUrl = url
                            showSetup = false
                        },
                    )
                } else {
                    AppNavGraph()
                }
            }
        }
    }
}
