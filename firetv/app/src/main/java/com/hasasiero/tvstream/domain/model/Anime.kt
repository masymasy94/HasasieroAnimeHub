package com.hasasiero.tvstream.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AnimeSearchResult(
    val id: Int,
    val slug: String,
    val title: String,
    @SerialName("title_eng") val titleEng: String? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    val type: String? = null,
    val year: String? = null,
    @SerialName("episodes_count") val episodesCount: Int? = null,
    val genres: List<String> = emptyList(),
    val dub: Boolean = false,
    @SerialName("source_site") val sourceSite: String = "animeunity",
)

@Serializable
data class AnimeDetail(
    val id: Int,
    val slug: String,
    val title: String,
    @SerialName("title_eng") val titleEng: String? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("banner_url") val bannerUrl: String? = null,
    val plot: String? = null,
    val type: String? = null,
    val year: String? = null,
    @SerialName("episodes_count") val episodesCount: Int? = null,
    val genres: List<String> = emptyList(),
    val status: String? = null,
    val dub: Boolean = false,
    @SerialName("source_site") val sourceSite: String = "animeunity",
)

@Serializable
data class Episode(
    val id: Int,
    val number: String,
    val title: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    val views: Int? = null,
)

@Serializable
data class SearchResponse(val results: List<AnimeSearchResult>)

@Serializable
data class EpisodesResponse(
    val episodes: List<Episode>,
    val total: Int,
    @SerialName("has_more") val hasMore: Boolean,
)

@Serializable
data class VideoSourceResponse(
    val url: String,
    val type: String,
    val headers: Map<String, String>? = null,
)

@Serializable
data class SitesResponse(
    val sites: List<Site>,
)

@Serializable
data class Site(
    val id: String,
    val name: String,
)
