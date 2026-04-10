package com.hasasiero.tvstream.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.tv.material3.*
import com.hasasiero.tvstream.domain.model.AnimeSearchResult
import com.hasasiero.tvstream.ui.components.ContentCard
import com.hasasiero.tvstream.ui.components.ContentRow
import com.hasasiero.tvstream.ui.theme.BgCard
import com.hasasiero.tvstream.ui.theme.TextSecondary
import com.hasasiero.tvstream.ui.theme.TextWhite

@Composable
fun HomeScreen(
    onAnimeClick: (AnimeSearchResult) -> Unit,
    onSettingsClick: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        if (state.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center),
            )
        } else if (state.error != null) {
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
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(vertical = 24.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                // Header: title + search + settings
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

                        // Search field
                        BasicTextField(
                            value = state.searchQuery,
                            onValueChange = { viewModel.onSearchQueryChange(it) },
                            textStyle = MaterialTheme.typography.bodyMedium.copy(
                                color = TextWhite,
                            ),
                            cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                            keyboardActions = KeyboardActions.Default,
                            decorationBox = { inner ->
                                Box(
                                    modifier = Modifier
                                        .width(300.dp)
                                        .background(BgCard, MaterialTheme.shapes.small)
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

                        Spacer(Modifier.weight(1f))

                        Button(
                            onClick = onSettingsClick,
                        ) {
                            Text("Impostazioni")
                        }
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

                // Latest anime
                if (state.latest.isNotEmpty()) {
                    // Group by source_site
                    val grouped = state.latest.groupBy { it.sourceSite }
                    grouped.forEach { (site, animes) ->
                        item {
                            ContentRow(
                                title = "Ultimi usciti — $site",
                                items = animes,
                                onItemClick = onAnimeClick,
                            )
                        }
                    }
                }
            }
        }
    }
}
