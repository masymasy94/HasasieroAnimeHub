package com.hasasiero.tvstream.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
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
    var editingUrl by remember { mutableStateOf(false) }
    var urlFocused by remember { mutableStateOf(false) }
    val urlFocusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

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
                if (editingUrl) {
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
                            keyboardController?.hide()
                            editingUrl = false
                        }),
                        modifier = Modifier.focusRequester(urlFocusRequester),
                        decorationBox = { inner ->
                            Box(
                                modifier = Modifier
                                    .width(500.dp)
                                    .background(BgCard, MaterialTheme.shapes.small)
                                    .border(2.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small)
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
                    LaunchedEffect(Unit) {
                        urlFocusRequester.requestFocus()
                        keyboardController?.show()
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .width(500.dp)
                            .background(BgCard, MaterialTheme.shapes.small)
                            .then(
                                if (urlFocused) Modifier.border(
                                    2.dp,
                                    MaterialTheme.colorScheme.primary,
                                    MaterialTheme.shapes.small,
                                ) else Modifier
                            )
                            .onFocusChanged { urlFocused = it.isFocused }
                            .focusable()
                            .clickable { editingUrl = true }
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                    ) {
                        Text(
                            if (serverUrl.isEmpty()) "http://192.168.x.x:8010" else serverUrl,
                            color = if (serverUrl.isEmpty()) TextSecondary else TextWhite,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                }
                Spacer(Modifier.width(16.dp))
                Button(onClick = {
                    serverConfig.baseUrl = serverUrl
                    saved = true
                    keyboardController?.hide()
                    editingUrl = false
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
