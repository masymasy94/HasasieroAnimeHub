package com.hasasiero.tvstream.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hasasiero.tvstream.data.repository.ContentRepository
import com.hasasiero.tvstream.domain.model.AnimeDetail
import com.hasasiero.tvstream.domain.model.Episode
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailUiState(
    val anime: AnimeDetail? = null,
    val episodes: List<Episode> = emptyList(),
    val totalEpisodes: Int = 0,
    val isLoading: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class DetailViewModel @Inject constructor(
    private val repository: ContentRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(DetailUiState())
    val state: StateFlow<DetailUiState> = _state

    fun load(animeId: Int, slug: String, site: String) {
        viewModelScope.launch {
            _state.value = DetailUiState(isLoading = true)
            try {
                val anime = repository.getAnimeDetail(animeId, slug, site)
                val episodesResp = repository.getEpisodes(animeId, slug, site)
                _state.value = DetailUiState(
                    anime = anime,
                    episodes = episodesResp.episodes,
                    totalEpisodes = episodesResp.total,
                    isLoading = false,
                )
            } catch (e: Exception) {
                _state.value = DetailUiState(isLoading = false, error = e.message)
            }
        }
    }
}
