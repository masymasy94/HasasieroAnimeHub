package com.hasasiero.tvstream.ui.theme

import androidx.compose.runtime.Composable
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.darkColorScheme

private val TvColorScheme = darkColorScheme(
    primary = Accent,
    onPrimary = White,
    secondary = AccentHover,
    background = BgPrimary,
    onBackground = TextPrimary,
    surface = BgSecondary,
    onSurface = TextWhite,
    surfaceVariant = BgCard,
    onSurfaceVariant = TextSecondary,
    error = Error,
    onError = White,
)

@Composable
fun TvStreamTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = TvColorScheme,
        content = content,
    )
}
