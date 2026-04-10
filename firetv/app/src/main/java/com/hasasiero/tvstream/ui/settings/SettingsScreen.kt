package com.hasasiero.tvstream.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.material3.*
import com.hasasiero.tvstream.data.remote.ServerConfig
import com.hasasiero.tvstream.ui.theme.BgCard
import com.hasasiero.tvstream.ui.theme.BgPrimary
import com.hasasiero.tvstream.ui.theme.TextSecondary
import com.hasasiero.tvstream.ui.theme.TextWhite

@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    serverConfig: ServerConfig = rememberServerConfig(),
) {
    var serverUrl by remember { mutableStateOf(serverConfig.baseUrl) }
    var saved by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgPrimary)
            .padding(48.dp),
    ) {
        Column {
            Text(
                "Impostazioni",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Spacer(Modifier.height(32.dp))

            Text(
                "Indirizzo server",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                BasicTextField(
                    value = serverUrl,
                    onValueChange = {
                        serverUrl = it
                        saved = false
                    },
                    textStyle = MaterialTheme.typography.bodyLarge.copy(color = TextWhite),
                    cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = {
                        serverConfig.baseUrl = serverUrl
                        saved = true
                    }),
                    decorationBox = { inner ->
                        Box(
                            modifier = Modifier
                                .width(500.dp)
                                .background(BgCard, MaterialTheme.shapes.small)
                                .padding(horizontal = 16.dp, vertical = 12.dp),
                        ) {
                            if (serverUrl.isEmpty()) {
                                Text(
                                    "http://192.168.x.x:8010",
                                    color = TextSecondary,
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                            }
                            inner()
                        }
                    },
                )
                Spacer(Modifier.width(16.dp))
                Button(onClick = {
                    serverConfig.baseUrl = serverUrl
                    saved = true
                }) {
                    Text("Salva")
                }
                if (saved) {
                    Spacer(Modifier.width(12.dp))
                    Text(
                        "Salvato! Riavvia l'app per applicare.",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
            Text(
                "URL attuale: ${serverConfig.baseUrl}",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
            )

            Spacer(Modifier.height(48.dp))
            Button(onClick = onBack) {
                Text("Indietro")
            }
        }
    }
}

@Composable
private fun rememberServerConfig(): ServerConfig {
    val context = androidx.compose.ui.platform.LocalContext.current
    return remember { ServerConfig(context) }
}
