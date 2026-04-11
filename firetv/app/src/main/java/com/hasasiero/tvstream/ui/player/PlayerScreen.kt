package com.hasasiero.tvstream.ui.player

import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(
    episodeId: Int,
    site: String,
    title: String,
    animeId: Int = 0,
    animeSlug: String = "",
    animeTitle: String = "",
    coverUrl: String = "",
    episodeNumber: String = "",
    onBack: () -> Unit,
    onNextEpisode: (() -> Unit)? = null,
    onPreviousEpisode: (() -> Unit)? = null,
    viewModel: PlayerViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Set metadata for watch history
    LaunchedEffect(episodeId) {
        viewModel.currentAnimeId = animeId
        viewModel.currentAnimeSlug = animeSlug
        viewModel.currentAnimeTitle = animeTitle
        viewModel.currentCoverUrl = coverUrl.ifEmpty { null }
        viewModel.currentSourceSite = site
        viewModel.currentEpisodeNumber = episodeNumber
        viewModel.currentEpisodeTitle = title
    }

    LaunchedEffect(episodeId, site) {
        viewModel.loadSource(episodeId, site)
    }

    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            playWhenReady = true
        }
    }

    // ForwardingPlayer that intercepts next/prev to trigger navigation
    val wrappedPlayer = remember(player, onNextEpisode, onPreviousEpisode) {
        object : ForwardingPlayer(player) {
            override fun getAvailableCommands(): Player.Commands {
                val builder = super.getAvailableCommands().buildUpon()
                if (onNextEpisode != null) builder.add(Player.COMMAND_SEEK_TO_NEXT)
                if (onPreviousEpisode != null) builder.add(Player.COMMAND_SEEK_TO_PREVIOUS)
                return builder.build()
            }

            override fun isCommandAvailable(command: Int): Boolean {
                if (command == Player.COMMAND_SEEK_TO_NEXT && onNextEpisode != null) return true
                if (command == Player.COMMAND_SEEK_TO_PREVIOUS && onPreviousEpisode != null) return true
                return super.isCommandAvailable(command)
            }

            override fun seekToNext() {
                onNextEpisode?.invoke()
            }

            override fun seekToNextMediaItem() {
                onNextEpisode?.invoke()
            }

            override fun seekToPrevious() {
                onPreviousEpisode?.invoke()
            }

            override fun seekToPreviousMediaItem() {
                onPreviousEpisode?.invoke()
            }

            override fun hasNextMediaItem(): Boolean = onNextEpisode != null
            override fun hasPreviousMediaItem(): Boolean = onPreviousEpisode != null
        }
    }

    // Save progress periodically
    LaunchedEffect(player) {
        while (true) {
            delay(5_000) // Save every 5s
            if (player.duration > 0) {
                viewModel.saveProgress(episodeId, player.currentPosition, player.duration)
            }
        }
    }

    // Set media source when URL ready
    LaunchedEffect(state.videoUrl, state.videoType) {
        val url = state.videoUrl ?: return@LaunchedEffect
        val mediaItem = MediaItem.fromUri(url)

        if (state.videoType == "m3u8") {
            val dataSourceFactory = DefaultHttpDataSource.Factory()
            val hlsSource = HlsMediaSource.Factory(dataSourceFactory)
                .createMediaSource(mediaItem)
            player.setMediaSource(hlsSource)
        } else {
            player.setMediaItem(mediaItem)
        }
        player.prepare()

        // Resume from saved position
        val savedPosition = viewModel.getSavedPosition(episodeId)
        if (savedPosition > 0) {
            player.seekTo(savedPosition)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (player.duration > 0) {
                scope.launch {
                    viewModel.saveProgress(episodeId, player.currentPosition, player.duration)
                }
            }
            player.release()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        if (state.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center),
                color = MaterialTheme.colorScheme.primary,
            )
        } else if (state.error != null) {
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
                Spacer(Modifier.height(16.dp))
                Button(onClick = onBack) { Text("Indietro") }
            }
        } else {
            // PlayerView — intercept ALL key events at View level
            var playerView by remember { mutableStateOf<PlayerView?>(null) }

            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        this.player = wrappedPlayer
                        useController = true
                        setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS)
                        controllerShowTimeoutMs = 5000
                        controllerAutoShow = true
                        setShowNextButton(onNextEpisode != null)
                        setShowPreviousButton(onPreviousEpisode != null)
                        isFocusable = true
                        isFocusableInTouchMode = true
                        descendantFocusability = android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS
                        // Intercept key events to show/hide controller
                        setOnKeyListener { _, keyCode, event ->
                            if (event.action == android.view.KeyEvent.ACTION_DOWN) {
                                when (keyCode) {
                                    android.view.KeyEvent.KEYCODE_BACK -> {
                                        if (isControllerFullyVisible) {
                                            hideController()
                                        } else {
                                            onBack()
                                        }
                                        true
                                    }
                                    else -> {
                                        if (!isControllerFullyVisible) {
                                            showController()
                                            true
                                        } else {
                                            false // let PlayerView handle it
                                        }
                                    }
                                }
                            } else false
                        }
                        requestFocus()
                        playerView = this
                    }
                },
                update = { view ->
                    view.player = wrappedPlayer
                    if (!view.hasFocus()) view.requestFocus()
                },
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}
