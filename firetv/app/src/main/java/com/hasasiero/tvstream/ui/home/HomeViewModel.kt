package com.hasasiero.tvstream.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hasasiero.tvstream.data.local.WatchHistoryDao
import com.hasasiero.tvstream.data.local.WatchHistoryEntry
import com.hasasiero.tvstream.data.repository.ContentRepository
import com.hasasiero.tvstream.domain.model.AnimeSearchResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val latest: List<AnimeSearchResult> = emptyList(),
    val searchResults: List<AnimeSearchResult> = emptyList(),
    val watchHistory: List<WatchHistoryEntry> = emptyList(),
    val searchQuery: String = "",
    val isSearching: Boolean = false,
    val isLoading: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: ContentRepository,
    private val watchHistoryDao: WatchHistoryDao,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state

    private var searchJob: Job? = null

    init {
        loadLatest()
        loadWatchHistory()
    }

    private fun loadWatchHistory() {
        viewModelScope.launch {
            try {
                val history = watchHistoryDao.getRecent()
                _state.value = _state.value.copy(watchHistory = history)
            } catch (_: Exception) {}
        }
    }

    private fun loadLatest() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val latest = repository.getLatest()
                _state.value = _state.value.copy(latest = latest, isLoading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Errore: ${e.javaClass.simpleName}: ${e.message}",
                )
            }
        }
    }

    fun onSearchQueryChange(query: String) {
        _state.value = _state.value.copy(searchQuery = query)
        searchJob?.cancel()
        if (query.isBlank()) {
            _state.value = _state.value.copy(searchResults = emptyList(), isSearching = false)
            return
        }
        searchJob = viewModelScope.launch {
            delay(400)
            _state.value = _state.value.copy(isSearching = true)
            try {
                val results = repository.search(query)
                _state.value = _state.value.copy(searchResults = results, isSearching = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(isSearching = false)
            }
        }
    }

    fun retry() {
        loadLatest()
        loadWatchHistory()
    }

    fun refresh() {
        loadWatchHistory()
    }
}
