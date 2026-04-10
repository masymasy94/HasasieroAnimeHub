package com.hasasiero.tvstream

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.hasasiero.tvstream.navigation.AppNavGraph
import com.hasasiero.tvstream.ui.theme.TvStreamTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TvStreamTheme {
                AppNavGraph()
            }
        }
    }
}
