package com.hasasiero.tvstream.ui.player

import android.app.Activity
import android.content.Context
import android.view.inputmethod.InputMethodManager
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
    onNavigateToEpisode: (episodeId: Int, episodeNumber: String) -> Unit,
    viewModel: PlayerViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val focusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

    val hasNext = state.nextEpisodeId > 0
    val hasPrev = state.prevEpisodeId > 0

    // Force-dismiss the soft keyboard on entry
    LaunchedEffect(Unit) {
        keyboardController?.hide()
        val imm = context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
        val window = (context as? Activity)?.window
        val token = window?.currentFocus?.windowToken ?: view.windowToken
        if (token != null) {
            imm?.hideSoftInputFromWindow(token, 0)
        }
        window?.currentFocus?.clearFocus()
    }

    // Overlay visibility
    var showOverlay by remember { mutableStateOf(true) }
    // Countdown auto-play state
    var showCountdown by remember { mutableStateOf(false) }
    var countdownSeconds by remember { mutableIntStateOf(5) }

    // Auto-hide overlay after 3s
    LaunchedEffect(showOverlay) {
        if (showOverlay) {
            delay(3000)
            showOverlay = false
        }
    }

    // Set metadata for watch history + resolve adjacent episodes
    LaunchedEffect(episodeId) {
        viewModel.currentAnimeId = animeId
        viewModel.currentAnimeSlug = animeSlug
        viewModel.currentAnimeTitle = animeTitle
        viewModel.currentCoverUrl = coverUrl.ifEmpty { null }
        viewModel.currentSourceSite = site
        viewModel.currentEpisodeNumber = episodeNumber
        viewModel.currentEpisodeTitle = title
        viewModel.resolveAdjacentEpisodes(episodeId)
    }

    LaunchedEffect(episodeId, site) {
        viewModel.loadSource(episodeId, site)
    }

    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            playWhenReady = true
        }
    }

    // Save progress periodically
    LaunchedEffect(player) {
        while (true) {
            delay(5_000)
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
        val savedPosition = viewModel.getSavedPosition(episodeId)
        if (savedPosition > 0) player.seekTo(savedPosition)
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

    // Detect video ended — trigger countdown if next episode available
    LaunchedEffect(player, hasNext) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED && hasNext) {
                    showOverlay = false
                    showCountdown = true
                    countdownSeconds = 5
                }
            }
        }
        player.addListener(listener)
    }

    // Countdown timer
    LaunchedEffect(showCountdown) {
        if (!showCountdown) return@LaunchedEffect
        countdownSeconds = 5
        while (countdownSeconds > 0) {
            delay(1000)
            countdownSeconds--
        }
        // Countdown finished — auto-play next
        showCountdown = false
        if (state.nextEpisodeId > 0) {
            onNavigateToEpisode(state.nextEpisodeId, state.nextEpisodeNumber)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(focusRequester)
            .focusable()
            .onPreviewKeyEvent { event ->
                if (event.type == KeyEventType.KeyDown) {
                    if (event.key == Key.Back) {
                        if (showCountdown) {
                            showCountdown = false
                            return@onPreviewKeyEvent true
                        }
                        if (showOverlay) {
                            showOverlay = false
                        } else {
                            onBack()
                        }
                        return@onPreviewKeyEvent true
                    }
                    if (showCountdown) return@onPreviewKeyEvent false
                    if (!showOverlay) {
                        showOverlay = true
                        return@onPreviewKeyEvent true
                    }
                    when (event.key) {
                        Key.DirectionCenter, Key.Enter -> {
                            if (player.isPlaying) player.pause() else player.play()
                            showOverlay = true
                            true
                        }
                        Key.DirectionLeft -> {
                            player.seekTo((player.currentPosition - 10_000).coerceAtLeast(0))
                            showOverlay = true
                            true
                        }
                        Key.DirectionRight -> {
                            player.seekTo(
                                (player.currentPosition + 10_000)
                                    .coerceAtMost(player.duration.coerceAtLeast(0))
                            )
                            showOverlay = true
                            true
                        }
                        else -> {
                            showOverlay = true
                            false
                        }
                    }
                } else false
            },
    ) {
        when {
            state.isLoading -> {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            state.error != null -> {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = onBack) { Text("Indietro") }
                }
            }
            else -> {
                AndroidView(
                    factory = { ctx ->
                        PlayerView(ctx).apply {
                            this.player = player
                            useController = false
                            setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS)
                        }
                    },
                    update = { v -> v.player = player },
                    modifier = Modifier.fillMaxSize(),
                )

                PlayerOverlay(
                    visible = showOverlay && !showCountdown,
                    title = title,
                    player = player,
                    hasNext = hasNext,
                    hasPrev = hasPrev,
                    onBack = {
                        if (showOverlay) showOverlay = false else onBack()
                    },
                    onNext = {
                        if (state.nextEpisodeId > 0) {
                            onNavigateToEpisode(state.nextEpisodeId, state.nextEpisodeNumber)
                        }
                    },
                    onPrev = {
                        if (state.prevEpisodeId > 0) {
                            onNavigateToEpisode(state.prevEpisodeId, state.prevEpisodeNumber)
                        }
                    },
                    onAnyInteraction = { showOverlay = true },
                )

                CountdownOverlay(
                    visible = showCountdown,
                    secondsLeft = countdownSeconds,
                    nextEpisodeLabel = "EP ${state.nextEpisodeNumber.ifEmpty { "?" }}",
                    onPlayNow = {
                        showCountdown = false
                        if (state.nextEpisodeId > 0) {
                            onNavigateToEpisode(state.nextEpisodeId, state.nextEpisodeNumber)
                        }
                    },
                    onCancel = {
                        showCountdown = false
                    },
                )
            }
        }
    }

    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
    }
}
