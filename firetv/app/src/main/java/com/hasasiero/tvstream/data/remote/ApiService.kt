package com.hasasiero.tvstream.data.remote

import com.hasasiero.tvstream.domain.model.*
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @GET("api/latest")
    suspend fun getLatest(): SearchResponse

    @GET("api/search")
    suspend fun search(@Query("title") title: String): SearchResponse

    @GET("api/sites")
    suspend fun getSites(): SitesResponse

    @GET("api/anime/{animePath}")
    suspend fun getAnimeDetail(
        @Path("animePath", encoded = true) animePath: String,
        @Query("site") site: String = "animeunity",
    ): AnimeDetail

    @GET("api/anime/{animePath}/episodes")
    suspend fun getEpisodes(
        @Path("animePath", encoded = true) animePath: String,
        @Query("start") start: Int = 1,
        @Query("end") end: Int? = null,
        @Query("site") site: String = "animeunity",
    ): EpisodesResponse

    @GET("api/stream/source/{episodeId}")
    suspend fun getStreamSource(
        @Path("episodeId") episodeId: Int,
        @Query("site") site: String = "animeunity",
    ): VideoSourceResponse
}
