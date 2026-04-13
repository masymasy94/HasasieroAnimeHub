package com.hasasiero.tvstream.ui.player

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.Player

@Composable
fun PlayerOverlay(
    visible: Boolean,
    title: String,
    player: Player,
    hasNext: Boolean,
    hasPrev: Boolean,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onPrev: () -> Unit,
    onAnyInteraction: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val isPlaying by rememberPlayerPlaying(player)
    val positionMs by rememberPlayerPosition(player)
    val durationMs by rememberPlayerDuration(player)

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = modifier.fillMaxSize(),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .onPreviewKeyEvent { event ->
                    if (event.type == KeyEventType.KeyDown) {
                        when (event.key) {
                            Key.Back -> {
                                onBack()
                                true
                            }
                            Key.DirectionCenter, Key.Enter -> {
                                if (player.isPlaying) player.pause() else player.play()
                                onAnyInteraction()
                                true
                            }
                            Key.DirectionLeft -> {
                                player.seekTo((player.currentPosition - 10_000).coerceAtLeast(0))
                                onAnyInteraction()
                                true
                            }
                            Key.DirectionRight -> {
                                player.seekTo(
                                    (player.currentPosition + 10_000)
                                        .coerceAtMost(player.duration.coerceAtLeast(0))
                                )
                                onAnyInteraction()
                                true
                            }
                            Key.DirectionUp -> {
                                if (hasPrev) onPrev()
                                onAnyInteraction()
                                true
                            }
                            Key.DirectionDown -> {
                                if (hasNext) onNext()
                                onAnyInteraction()
                                true
                            }
                            else -> {
                                onAnyInteraction()
                                false
                            }
                        }
                    } else false
                }
                .focusable(),
        ) {
            // ── Top: gradient + title ──
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .background(
                        Brush.verticalGradient(
                            listOf(Color.Black.copy(alpha = 0.7f), Color.Transparent)
                        )
                    )
                    .align(Alignment.TopCenter)
                    .padding(horizontal = 48.dp, vertical = 24.dp),
            ) {
                Text(
                    text = title,
                    color = Color.White,
                    fontSize = 20.sp,
                )
            }

            // ── Center: transport controls ──
            Row(
                modifier = Modifier.align(Alignment.Center),
                horizontalArrangement = Arrangement.spacedBy(40.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (hasPrev) {
                    TransportIcon("⏮", "Precedente") { onPrev() }
                }
                TransportIcon("↺10", "Indietro 10s") {
                    player.seekTo((player.currentPosition - 10_000).coerceAtLeast(0))
                    onAnyInteraction()
                }
                // Play/Pause — larger
                Box(
                    modifier = Modifier
                        .size(72.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.15f))
                        .clickable {
                            if (player.isPlaying) player.pause() else player.play()
                            onAnyInteraction()
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = if (isPlaying) "❚❚" else "▶",
                        color = Color.White,
                        fontSize = 28.sp,
                    )
                }
                TransportIcon("10↻", "Avanti 10s") {
                    player.seekTo(
                        (player.currentPosition + 10_000)
                            .coerceAtMost(player.duration.coerceAtLeast(0))
                    )
                    onAnyInteraction()
                }
                if (hasNext) {
                    TransportIcon("⏭", "Prossimo") { onNext() }
                }
            }

            // ── Bottom: seekbar + time ──
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(Color.Transparent, Color.Black.copy(alpha = 0.7f))
                        )
                    )
                    .align(Alignment.BottomCenter)
                    .padding(horizontal = 48.dp, vertical = 16.dp),
            ) {
                // Seekbar
                val progress = if (durationMs > 0) positionMs.toFloat() / durationMs else 0f
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Color.White.copy(alpha = 0.3f)),
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxHeight()
                            .fillMaxWidth(fraction = progress)
                            .clip(RoundedCornerShape(2.dp))
                            .background(Color(0xFFE5A00D)), // Plex gold
                    )
                }
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(formatTime(positionMs), color = Color.White, fontSize = 13.sp)
                    Text("-${formatTime(durationMs - positionMs)}", color = Color.White.copy(alpha = 0.7f), fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
private fun TransportIcon(text: String, description: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.1f))
            .clickable { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = Color.White, fontSize = 16.sp)
    }
}

@Composable
private fun rememberPlayerPlaying(player: Player): State<Boolean> {
    val state = remember { mutableStateOf(player.isPlaying) }
    LaunchedEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                state.value = isPlaying
            }
        }
        player.addListener(listener)
    }
    return state
}

@Composable
private fun rememberPlayerPosition(player: Player): State<Long> {
    val state = remember { mutableLongStateOf(0L) }
    LaunchedEffect(player) {
        while (true) {
            state.longValue = player.currentPosition
            kotlinx.coroutines.delay(500)
        }
    }
    return state
}

@Composable
private fun rememberPlayerDuration(player: Player): State<Long> {
    val state = remember { mutableLongStateOf(0L) }
    LaunchedEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                state.longValue = player.duration.coerceAtLeast(0)
            }
        }
        player.addListener(listener)
        state.longValue = player.duration.coerceAtLeast(0)
    }
    return state
}

@Composable
fun CountdownOverlay(
    visible: Boolean,
    secondsLeft: Int,
    nextEpisodeLabel: String,
    onPlayNow: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val playFocus = remember { FocusRequester() }

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = modifier.fillMaxSize(),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.85f))
                .onPreviewKeyEvent { event ->
                    if (event.type == KeyEventType.KeyDown) {
                        when (event.key) {
                            Key.Back -> { onCancel(); true }
                            else -> false
                        }
                    } else false
                },
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = "Prossimo episodio tra",
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 16.sp,
                )
                Text(
                    text = "$secondsLeft",
                    color = Color.White,
                    fontSize = 56.sp,
                    style = MaterialTheme.typography.headlineLarge,
                )
                Text(
                    text = nextEpisodeLabel,
                    color = Color.White.copy(alpha = 0.9f),
                    fontSize = 18.sp,
                )
                Spacer(Modifier.height(8.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .focusRequester(playFocus)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color(0xFFE5A00D))
                            .clickable { onPlayNow() }
                            .onFocusChanged {
                                // visual feedback handled by Compose focus
                            }
                            .focusable()
                            .padding(horizontal = 24.dp, vertical = 12.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("Riproduci ora", color = Color.Black, fontSize = 15.sp)
                    }
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color.White.copy(alpha = 0.15f))
                            .clickable { onCancel() }
                            .focusable()
                            .padding(horizontal = 24.dp, vertical = 12.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("Annulla", color = Color.White, fontSize = 15.sp)
                    }
                }
            }

            // Progress bar at bottom
            val fraction = secondsLeft / 5f
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .align(Alignment.BottomCenter),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .fillMaxWidth()
                        .background(Color.White.copy(alpha = 0.1f)),
                )
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .fillMaxWidth(fraction = fraction)
                        .background(Color(0xFFE5A00D)),
                )
            }
        }

        // Focus the play button when visible
        LaunchedEffect(visible) {
            if (visible) {
                kotlinx.coroutines.delay(100)
                try { playFocus.requestFocus() } catch (_: Exception) {}
            }
        }
    }
}

private fun formatTime(ms: Long): String {
    if (ms <= 0) return "0:00"
    val totalSeconds = ms / 1000
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds)
    else "%d:%02d".format(minutes, seconds)
}
