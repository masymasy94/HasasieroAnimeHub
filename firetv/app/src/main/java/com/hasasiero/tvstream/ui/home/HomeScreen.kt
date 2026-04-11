package com.hasasiero.tvstream.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.hasasiero.tvstream.data.local.WatchHistoryEntry
import com.hasasiero.tvstream.domain.model.AnimeSearchResult
import com.hasasiero.tvstream.ui.components.ContentRow
import com.hasasiero.tvstream.ui.components.ContinueWatchingRow
import com.hasasiero.tvstream.ui.theme.BgCard
import com.hasasiero.tvstream.ui.theme.TextSecondary
import com.hasasiero.tvstream.ui.theme.TextWhite

@Composable
fun HomeScreen(
    onAnimeClick: (AnimeSearchResult) -> Unit,
    onContinueWatching: (WatchHistoryEntry) -> Unit = {},
    onSettingsClick: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    // Refresh watch history every time this screen becomes visible
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            viewModel.refresh()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
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
                    Text(
                        text = state.error ?: "",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = { viewModel.retry() }) {
                        Text("Riprova")
                    }
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onSettingsClick) {
                        Text("Impostazioni")
                    }
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(vertical = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    // Header
                    item {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 48.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "AnimeHub",
                                style = MaterialTheme.typography.headlineLarge,
                                color = MaterialTheme.colorScheme.primary,
                            )
                            Spacer(Modifier.width(24.dp))

                            // Search box — focus shows border, click opens keyboard
                            var searchActive by remember { mutableStateOf(false) }
                            var searchFocused by remember { mutableStateOf(false) }
                            val searchFocusRequester = remember { FocusRequester() }
                            val keyboardController = LocalSoftwareKeyboardController.current

                            if (searchActive) {
                                BasicTextField(
                                    value = state.searchQuery,
                                    onValueChange = { viewModel.onSearchQueryChange(it) },
                                    textStyle = MaterialTheme.typography.bodyMedium.copy(
                                        color = TextWhite,
                                    ),
                                    cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                                    keyboardActions = KeyboardActions(onSearch = {
                                        keyboardController?.hide()
                                    }),
                                    modifier = Modifier
                                        .width(300.dp)
                                        .focusRequester(searchFocusRequester),
                                    decorationBox = { inner ->
                                        Box(
                                            modifier = Modifier
                                                .background(BgCard, MaterialTheme.shapes.small)
                                                .border(1.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small)
                                                .padding(horizontal = 16.dp, vertical = 10.dp),
                                        ) {
                                            if (state.searchQuery.isEmpty()) {
                                                Text(
                                                    "Cerca anime...",
                                                    color = TextSecondary,
                                                    style = MaterialTheme.typography.bodyMedium,
                                                )
                                            }
                                            inner()
                                        }
                                    },
                                )
                                LaunchedEffect(Unit) {
                                    searchFocusRequester.requestFocus()
                                }
                            } else {
                                Box(
                                    modifier = Modifier
                                        .width(300.dp)
                                        .background(BgCard, MaterialTheme.shapes.small)
                                        .then(
                                            if (searchFocused) Modifier.border(1.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small)
                                            else Modifier
                                        )
                                        .onFocusChanged { searchFocused = it.isFocused }
                                        .focusable()
                                        .clickable { searchActive = true }
                                        .padding(horizontal = 16.dp, vertical = 10.dp),
                                ) {
                                    Text(
                                        if (state.searchQuery.isEmpty()) "Cerca anime..." else state.searchQuery,
                                        color = if (state.searchQuery.isEmpty()) TextSecondary else TextWhite,
                                        style = MaterialTheme.typography.bodyMedium,
                                    )
                                }
                            }

                            Spacer(Modifier.weight(1f))

                            Button(onClick = onSettingsClick) {
                                Text("Impostazioni")
                            }
                        }
                    }

                    // Continue watching
                    if (state.watchHistory.isNotEmpty()) {
                        item {
                            ContinueWatchingRow(
                                items = state.watchHistory,
                                onItemClick = onContinueWatching,
                            )
                        }
                    }

                    // Search results
                    if (state.searchResults.isNotEmpty()) {
                        item {
                            ContentRow(
                                title = "Risultati ricerca",
                                items = state.searchResults,
                                onItemClick = onAnimeClick,
                            )
                        }
                    }

                    // Latest anime - flat list, no grouping that could cause issues
                    if (state.latest.isNotEmpty()) {
                        item {
                            ContentRow(
                                title = "Ultimi usciti",
                                items = state.latest,
                                onItemClick = onAnimeClick,
                            )
                        }
                    }

                    // Empty state
                    if (state.latest.isEmpty() && state.searchResults.isEmpty()) {
                        item {
                            Text(
                                text = "Nessun anime trovato",
                                modifier = Modifier.padding(horizontal = 48.dp),
                                color = TextSecondary,
                            )
                        }
                    }
                }
            }
        }
    }
}
