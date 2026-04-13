package com.hasasiero.tvstream.ui.player

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hasasiero.tvstream.data.local.WatchHistoryDao
import com.hasasiero.tvstream.data.local.WatchHistoryEntry
import com.hasasiero.tvstream.data.remote.ServerConfig
import com.hasasiero.tvstream.data.repository.ContentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlayerUiState(
    val videoUrl: String? = null,
    val videoType: String? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
    val nextEpisodeId: Int = -1,
    val nextEpisodeNumber: String = "",
    val prevEpisodeId: Int = -1,
    val prevEpisodeNumber: String = "",
)

@HiltViewModel
class PlayerViewModel @Inject constructor(
    private val repository: ContentRepository,
    private val serverConfig: ServerConfig,
    private val watchHistoryDao: WatchHistoryDao,
) : ViewModel() {

    private val _state = MutableStateFlow(PlayerUiState())
    val state: StateFlow<PlayerUiState> = _state

    // Cache for current episode metadata (set by DetailScreen before navigating)
    var currentAnimeId: Int = 0
    var currentAnimeSlug: String = ""
    var currentAnimeTitle: String = ""
    var currentCoverUrl: String? = null
    var currentSourceSite: String = ""
    var currentEpisodeNumber: String = ""
    var currentEpisodeTitle: String? = null

    fun loadSource(episodeId: Int, site: String) {
        viewModelScope.launch {
            _state.value = PlayerUiState(isLoading = true)
            try {
                val source = repository.getStreamUrl(episodeId, site)
                val fullUrl = if (source.url.startsWith("/")) {
                    "${serverConfig.baseUrl}${source.url}"
                } else {
                    source.url
                }
                _state.value = PlayerUiState(
                    videoUrl = fullUrl,
                    videoType = source.type,
                    isLoading = false,
                )
            } catch (e: Exception) {
                _state.value = PlayerUiState(
                    isLoading = false,
                    error = "Impossibile caricare il video: ${e.message}",
                )
            }
        }
    }

    /**
     * Fetch the episode list for the current anime and resolve next/prev
     * relative to [currentEpisodeId]. Updates state with the IDs.
     */
    fun resolveAdjacentEpisodes(currentEpisodeId: Int) {
        if (currentAnimeId == 0 || currentAnimeSlug.isEmpty()) return
        viewModelScope.launch {
            try {
                val resp = repository.getEpisodes(
                    animeId = currentAnimeId,
                    slug = currentAnimeSlug,
                    site = currentSourceSite.ifEmpty { "animeunity" },
                )
                val episodes = resp.episodes
                val idx = episodes.indexOfFirst { it.id == currentEpisodeId }
                if (idx < 0) return@launch

                val next = episodes.getOrNull(idx + 1)
                val prev = episodes.getOrNull(idx - 1)

                _state.value = _state.value.copy(
                    nextEpisodeId = next?.id ?: -1,
                    nextEpisodeNumber = next?.number ?: "",
                    prevEpisodeId = prev?.id ?: -1,
                    prevEpisodeNumber = prev?.number ?: "",
                )
            } catch (e: Exception) {
                // Non-critical — just means no auto-play
            }
        }
    }

    suspend fun getSavedPosition(episodeId: Int): Long {
        return watchHistoryDao.getByEpisodeId(episodeId)?.positionMs ?: 0L
    }

    fun saveProgress(episodeId: Int, positionMs: Long, durationMs: Long) {
        viewModelScope.launch {
            watchHistoryDao.upsert(
                WatchHistoryEntry(
                    episodeId = episodeId,
                    animeId = currentAnimeId,
                    animeSlug = currentAnimeSlug,
                    animeTitle = currentAnimeTitle,
                    coverUrl = currentCoverUrl,
                    sourceSite = currentSourceSite,
                    episodeNumber = currentEpisodeNumber,
                    episodeTitle = currentEpisodeTitle,
                    positionMs = positionMs,
                    durationMs = durationMs,
                    lastWatchedAt = System.currentTimeMillis(),
                )
            )
        }
    }
}
