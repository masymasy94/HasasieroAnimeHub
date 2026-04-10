package com.hasasiero.tvstream.data.repository

import com.hasasiero.tvstream.data.remote.ApiService
import com.hasasiero.tvstream.domain.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ContentRepository @Inject constructor(
    private val api: ApiService,
) {
    suspend fun getLatest(): List<AnimeSearchResult> =
        api.getLatest().results

    suspend fun search(query: String): List<AnimeSearchResult> =
        api.search(query).results

    suspend fun getSites(): List<Site> =
        api.getSites().sites

    suspend fun getAnimeDetail(animeId: Int, slug: String, site: String): AnimeDetail =
        api.getAnimeDetail("$animeId-$slug", site)

    suspend fun getEpisodes(
        animeId: Int,
        slug: String,
        site: String,
        start: Int = 1,
        end: Int? = null,
    ): EpisodesResponse = api.getEpisodes("$animeId-$slug", start, end, site)

    suspend fun getStreamUrl(episodeId: Int, site: String): VideoSourceResponse =
        api.getStreamSource(episodeId, site)
}
