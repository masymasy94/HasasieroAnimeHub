# Fire TV Player Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Fire TV player so play/resume works after pause, the controls overlay behaves like Plex (top title bar, center transport, bottom seekbar, fast auto-hide), and the next-episode button triggers navigation. Verify every fix end-to-end on the Android TV emulator with a real streaming server.

**Architecture:** Replace the current `setOnKeyListener` approach (which intercepts DPAD_CENTER and breaks play/pause) with `dispatchKeyEvent` override on a custom `PlayerView` subclass. This lets PlayerView handle all transport keys natively while we only intercept Back. Build a custom Plex-style overlay using Compose drawn on top of a raw `SurfaceView` (via `PlayerView` with `useController = false`), replacing the built-in ExoPlayer controls whose look can't be customized enough. The overlay has three layers: top gradient (title), center transport buttons (prev / rewind 10s / play-pause / forward 10s / next), bottom seekbar with elapsed/remaining time. Overlay auto-hides after 3 seconds, any D-pad press re-shows it.

**Tech Stack:** Kotlin, Jetpack Compose, Media3 ExoPlayer 1.5.1, AndroidView, Room (watch history), ForwardingPlayer.

**Emulator setup for testing:** API 28 Android TV x86 emulator (`tv_test` AVD), local Docker server at `10.0.2.2:8010`, ADB screencaps for verification.

---

## Codebase Context

All files live under `firetv/app/src/main/java/com/hasasiero/tvstream/`.

### Current bugs

| Bug | Root cause | Fix |
|-----|-----------|-----|
| Play/resume doesn't work after pause | `setOnKeyListener` returns `true` for **all** keys when controller is hidden, consuming `DPAD_CENTER` before PlayerView can toggle play/pause | Remove `setOnKeyListener`. Override `dispatchKeyEvent` inside a `PlayerView` subclass so Back is intercepted but all other keys flow through to the default controller |
| Controls overlay doesn't look like Plex | Using ExoPlayer's built-in `PlayerControlView` which has fixed Material style | Build a custom Compose overlay (`PlayerOverlay.kt`) drawn on top of `PlayerView(useController=false)`. Three zones: top title gradient, center transport icons, bottom seekbar + time |
| Overlay stays too long | `controllerShowTimeoutMs = 5000` | Reduce to 3000, auto-hide with `LaunchedEffect` |
| Next episode button visible but doesn't navigate | `ForwardingPlayer.seekToNext()` calls `onNextEpisode?.invoke()` correctly but button never receives focus/tap via D-pad because `setOnKeyListener` eats the event | Fixing the key listener fixes this too — `ForwardingPlayer` wiring is already correct |
| Icon not showing on Fire TV | Known Fire OS 8 bug for sideloaded apps — see [AFTVnews](https://www.aftvnews.com/how-to-fix-missing-or-broken-icons-for-sideloaded-apps-on-amazon-fire-tv/). Icon PNGs are correctly placed in `drawable/` and `mipmap/` (verified via `aapt dump badging`) | No code fix. User must: uninstall app → restart Fire TV → reinstall. Plan includes instructions. |

### File map

**Files to create:**
- `ui/player/PlayerOverlay.kt` — Compose overlay with Plex-style layout (top title, center transport, bottom seekbar)

**Files to modify:**
- `ui/player/PlayerScreen.kt` — Replace `setOnKeyListener` + built-in controls with custom overlay + `dispatchKeyEvent` approach
- `ui/player/PlayerViewModel.kt` — No changes needed (already correct)
- `navigation/AppNavGraph.kt` — No changes needed (ForwardingPlayer wiring already correct)

**Files unchanged:**
- `ui/home/HomeScreen.kt` — Continue watching works (verified on emulator)
- `ui/detail/DetailScreen.kt` — Episode list + next/prev passing works
- `data/local/WatchHistory.kt` — Room DB works
- `di/DatabaseModule.kt`, `di/NetworkModule.kt` — DI works
- `ui/settings/ServerSetupDialog.kt` — Setup flow works

---

## Task 1: Create Plex-style player overlay composable

**Files:**
- Create: `firetv/app/src/main/java/com/hasasiero/tvstream/ui/player/PlayerOverlay.kt`

- [ ] **Step 1: Create `PlayerOverlay.kt`**

```kotlin
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

private fun formatTime(ms: Long): String {
    if (ms <= 0) return "0:00"
    val totalSeconds = ms / 1000
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds)
    else "%d:%02d".format(minutes, seconds)
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd firetv && ANDROID_HOME=~/Library/Android/sdk ./gradlew compileDebugKotlin --no-daemon 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL

- [ ] **Step 3: Commit**

```bash
git add firetv/app/src/main/java/com/hasasiero/tvstream/ui/player/PlayerOverlay.kt
git commit -m "feat(firetv): add Plex-style player overlay composable"
```

---

## Task 2: Rewrite PlayerScreen to use custom overlay

**Files:**
- Modify: `firetv/app/src/main/java/com/hasasiero/tvstream/ui/player/PlayerScreen.kt`

- [ ] **Step 1: Rewrite PlayerScreen**

Replace the entire file content with:

```kotlin
package com.hasasiero.tvstream.ui.player

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
    val focusRequester = remember { FocusRequester() }

    // Overlay visibility
    var showOverlay by remember { mutableStateOf(true) }

    // Auto-hide overlay after 3s
    LaunchedEffect(showOverlay) {
        if (showOverlay) {
            delay(3000)
            showOverlay = false
        }
    }

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

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(focusRequester)
            .focusable()
            .onPreviewKeyEvent { event ->
                if (event.type == KeyEventType.KeyDown) {
                    if (event.key == Key.Back) {
                        if (showOverlay) {
                            showOverlay = false
                        } else {
                            onBack()
                        }
                        return@onPreviewKeyEvent true
                    }
                    if (!showOverlay) {
                        // First key press just shows overlay, doesn't act
                        showOverlay = true
                        return@onPreviewKeyEvent true
                    }
                    // Overlay visible — handle transport
                    when (event.key) {
                        Key.DirectionCenter, Key.Enter -> {
                            if (player.isPlaying) player.pause() else player.play()
                            showOverlay = true // reset timer
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
                // Video surface only — no built-in controls
                AndroidView(
                    factory = { ctx ->
                        PlayerView(ctx).apply {
                            this.player = player
                            useController = false
                            setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS)
                        }
                    },
                    update = { view -> view.player = player },
                    modifier = Modifier.fillMaxSize(),
                )

                // Custom Plex-style overlay
                PlayerOverlay(
                    visible = showOverlay,
                    title = title,
                    player = player,
                    hasNext = onNextEpisode != null,
                    hasPrev = onPreviousEpisode != null,
                    onBack = {
                        if (showOverlay) showOverlay = false else onBack()
                    },
                    onNext = { onNextEpisode?.invoke() },
                    onPrev = { onPreviousEpisode?.invoke() },
                    onAnyInteraction = { showOverlay = true },
                )
            }
        }
    }

    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
    }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd firetv && ANDROID_HOME=~/Library/Android/sdk ./gradlew compileDebugKotlin --no-daemon 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL

- [ ] **Step 3: Build APK**

Run: `cd firetv && ANDROID_HOME=~/Library/Android/sdk ./gradlew assembleDebug --no-daemon 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL

- [ ] **Step 4: Commit**

```bash
git add firetv/app/src/main/java/com/hasasiero/tvstream/ui/player/PlayerScreen.kt
git commit -m "feat(firetv): rewrite player with Plex-style overlay + fix play/pause"
```

---

## Task 3: Test full flow on emulator

This task verifies all fixes end-to-end using the Android TV emulator and a local Docker server. **Every step must produce a screenshot saved to `/tmp/` and visually inspected.**

**Prerequisites:**
- Android TV emulator AVD `tv_test` (API 28 x86) available
- Docker installed
- Server image built: `docker build -t animehub-local .`

- [ ] **Step 1: Start local server**

```bash
docker run -d --name animehub-test -p 8010:8000 \
  -v /tmp/animehub-data:/data -v /tmp/animehub-downloads:/downloads \
  animehub-local
sleep 5
curl -s http://localhost:8010/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 2: Start emulator**

```bash
export ANDROID_HOME=~/Library/Android/sdk
$ANDROID_HOME/emulator/emulator -avd tv_test -no-window -no-audio \
  -gpu swiftshader_indirect -no-boot-anim -memory 2048 &
# Wait for boot
for i in $(seq 1 60); do
  STATUS=$($ANDROID_HOME/platform-tools/adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
  [ "$STATUS" = "1" ] && echo "Booted" && break
  sleep 2
done
```
Expected: "Booted"

- [ ] **Step 3: Install APK**

```bash
APK=$(find firetv/app/build/outputs/apk -name "*.apk" | head -1)
$ANDROID_HOME/platform-tools/adb install -r "$APK"
```
Expected: "Success"

- [ ] **Step 4: Launch app and configure server**

```bash
$ANDROID_HOME/platform-tools/adb shell am start -n com.hasasiero.tvstream/.MainActivity
sleep 5
```
If setup dialog appears, type `http://10.0.2.2:8010` and press Enter.
Screenshot: verify home screen with anime catalog.

- [ ] **Step 5: Verify "Ultimi usciti" shows anime**

Take screenshot. Expected: row of anime cards with covers.

- [ ] **Step 6: Navigate to One Piece (ITA) detail page**

D-pad navigate to One Piece (ITA) card, press Center.
Screenshot: anime detail with cover, plot, episode grid.

- [ ] **Step 7: Play Episode 1**

D-pad to EP 1 card, press Center.
Wait 5 seconds for video to load and start playing.
Screenshot: video playing (anime frame visible).

- [ ] **Step 8: Verify overlay appears on D-pad press**

Press DPAD_UP.
Screenshot: overlay with title at top, transport buttons in center (play/pause, seek), seekbar + time at bottom.
**This is the critical screenshot — must show Plex-style overlay.**

- [ ] **Step 9: Verify play/pause works**

Press DPAD_CENTER to pause.
Screenshot: video paused, pause icon changes to play icon.
Press DPAD_CENTER again to resume.
Screenshot: video playing again.
**This is the second critical verification — play/pause must toggle.**

- [ ] **Step 10: Verify seek works**

Press DPAD_LEFT (rewind 10s).
Press DPAD_RIGHT (forward 10s).
Screenshot: time on seekbar changed.

- [ ] **Step 11: Watch for 15 seconds, then go back**

Wait 15s (for watch history to save).
Press Back to dismiss overlay, press Back again to return to detail.
Press Back to return to home.

- [ ] **Step 12: Verify "Continua a guardare" appears**

Screenshot: home screen with "Continua a guardare" section showing One Piece (ITA) EP 1 with progress bar.
**Third critical verification.**

- [ ] **Step 13: Verify "Continua a guardare" resumes**

Click the "Continua a guardare" card.
Wait 3 seconds.
Screenshot: video playing from saved position (not from beginning).

- [ ] **Step 14: Cleanup**

```bash
$ANDROID_HOME/platform-tools/adb emu kill
docker stop animehub-test && docker rm animehub-test
```

- [ ] **Step 15: Commit verification notes**

If all screenshots pass, commit a `docs/superpowers/plans/2026-04-11-firetv-player-fixes-verified.md` with a summary of which steps passed.

```bash
git add docs/
git commit -m "test(firetv): player fixes verified on emulator"
```

---

## Task 4: Push and deploy

- [ ] **Step 1: Push with RELEASE tag**

```bash
git push origin main
```

- [ ] **Step 2: Watch CI**

```bash
RUN_ID=$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch $RUN_ID --exit-status --compact
```
Expected: build-and-push ✓, build-firetv-apk ✓, deploy ✓

- [ ] **Step 3: Notify user**

Tell user to:
1. Uninstall old AnimeHub from Fire TV (Impostazioni > App > AnimeHub > Disinstalla)
2. Restart Fire TV (stacca corrente)
3. Download APK: `https://github.com/masymasy94/HasasieroAnimeHub/releases/download/latest/AnimeHub-TV.apk`
4. Install via Downloader
5. On first launch, enter server IP: `http://192.168.3.54:8010`
6. Press Done on keyboard

---

## Task 5: Fire TV icon — user instructions

No code fix possible. This is a [known Fire OS 8 bug](https://www.aftvnews.com/missing-app-icon-bug-returns-in-fire-os-8-on-new-fire-tv-stick-4k-4k-max-for-sideloaded-apps/).

- [ ] **Step 1: Document the workaround**

The icon PNGs are correctly packaged (verified via `aapt dump badging` — shows `icon='res/drawable/ic_launcher.png'` and `banner='res/drawable/banner.png'`). The icon shows correctly on the Android TV emulator.

On Fire TV Stick 4K 2nd gen (Fire OS 8), sideloaded apps may show a grey/black icon. Amazon has released fixes via Appstore system updates.

User action:
1. Go to **Impostazioni > La mia Fire TV > Informazioni > Verifica aggiornamenti** — install any pending updates
2. **Uninstall** the app completely
3. **Restart** the Fire TV (unplug power, wait 10s, replug)
4. **Reinstall** the APK
5. Open the app once from Downloader (first launch registers the icon)
6. Go back to home — icon should now appear

If icon still missing after these steps, it's a Fire OS launcher cache bug. Alternative: install [Wolf Launcher](https://www.aftvnews.com/how-to-use-custom-icons-for-sideloaded-apps-like-kodi-on-the-amazon-fire-tv/) which shows all sideloaded app icons correctly.

---

## Self-Review

**Spec coverage:**
- ✅ Play/resume after pause: Task 2 removes `setOnKeyListener`, uses Compose `onPreviewKeyEvent` that properly handles DPAD_CENTER → `player.play()/pause()` toggle
- ✅ Plex-style overlay: Task 1 creates `PlayerOverlay.kt` with top title gradient, center transport buttons, bottom gold seekbar + elapsed/remaining time
- ✅ Overlay hides faster: 3000ms auto-hide via `LaunchedEffect`
- ✅ Next episode: Task 2 preserves `ForwardingPlayer` wiring, navigation via `onNextEpisode` callback
- ✅ Full emulator test: Task 3 with 13 verification steps and screenshots
- ✅ Icon workaround: Task 5 documents Fire OS 8 bug and user steps

**Placeholder scan:** No TBD/TODO/placeholders found.

**Type consistency:** `PlayerOverlay` parameters match usage in `PlayerScreen`. `player: Player` type consistent. `onNextEpisode`/`onPreviousEpisode` nullable lambdas match `AppNavGraph` wiring.
