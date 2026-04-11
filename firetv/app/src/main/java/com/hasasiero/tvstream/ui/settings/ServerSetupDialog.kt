package com.hasasiero.tvstream.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.hasasiero.tvstream.ui.theme.*

@Composable
fun ServerSetupDialog(
    currentUrl: String,
    onConfirm: (String) -> Unit,
) {
    var url by remember { mutableStateOf(currentUrl) }
    var buttonFocused by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgPrimary),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier
                .width(500.dp)
                .background(BgSecondary, RoundedCornerShape(12.dp))
                .padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "AnimeHub",
                style = MaterialTheme.typography.headlineLarge,
                color = Accent,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "HASASIERO",
                style = MaterialTheme.typography.labelSmall,
                color = TextSecondary,
            )
            Spacer(Modifier.height(32.dp))

            Text(
                "Indirizzo server",
                style = MaterialTheme.typography.titleSmall,
                color = TextWhite,
            )
            Spacer(Modifier.height(12.dp))

            BasicTextField(
                value = url,
                onValueChange = { url = it },
                textStyle = MaterialTheme.typography.bodyLarge.copy(color = TextWhite),
                cursorBrush = SolidColor(Accent),
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = {
                    if (url.isNotBlank()) onConfirm(url.trimEnd('/'))
                }),
                decorationBox = { inner ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(BgCard, RoundedCornerShape(8.dp))
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                    ) {
                        if (url.isEmpty()) {
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

            Spacer(Modifier.height(8.dp))
            Text(
                "Inserisci l'IP del server AnimeHub sulla tua rete locale",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
            )

            Spacer(Modifier.height(24.dp))

            // Focusable button that works with D-pad
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .background(
                        if (buttonFocused) AccentHover else Accent,
                        RoundedCornerShape(24.dp),
                    )
                    .then(
                        if (buttonFocused) Modifier.border(2.dp, White, RoundedCornerShape(24.dp))
                        else Modifier
                    )
                    .onFocusChanged { buttonFocused = it.isFocused }
                    .focusable()
                    .clickable {
                        if (url.isNotBlank()) onConfirm(url.trimEnd('/'))
                    },
                contentAlignment = Alignment.Center,
            ) {
                Text("Connetti", color = White, style = MaterialTheme.typography.titleSmall)
            }
        }
    }
}
