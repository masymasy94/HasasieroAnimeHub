package com.hasasiero.tvstream.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hasasiero.tvstream.domain.model.AnimeSearchResult

@Composable
fun ContentRow(
    title: String,
    items: List<AnimeSearchResult>,
    onItemClick: (AnimeSearchResult) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(start = 48.dp, bottom = 12.dp),
        )
        LazyRow(
            contentPadding = PaddingValues(horizontal = 48.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            items(items, key = { "${it.id}-${it.sourceSite}" }) { anime ->
                ContentCard(
                    title = anime.title,
                    coverUrl = anime.coverUrl,
                    subtitle = anime.sourceSite,
                    onClick = { onItemClick(anime) },
                )
            }
        }
    }
}
