package com.hasasiero.tvstream.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import com.hasasiero.tvstream.ui.detail.DetailScreen
import com.hasasiero.tvstream.ui.home.HomeScreen
import com.hasasiero.tvstream.ui.player.PlayerScreen
import com.hasasiero.tvstream.ui.settings.SettingsScreen
import kotlinx.serialization.Serializable

@Serializable
object Home

@Serializable
data class Detail(val animeId: Int, val slug: String, val site: String)

@Serializable
data class Player(
    val episodeId: Int,
    val site: String,
    val title: String,
    val animeId: Int,
    val animeSlug: String,
    val animeTitle: String,
    val coverUrl: String = "",
    val episodeNumber: String = "",
)

@Serializable
object Settings

@Composable
fun AppNavGraph() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Home) {
        composable<Home> {
            HomeScreen(
                onAnimeClick = { anime ->
                    navController.navigate(Detail(anime.id, anime.slug, anime.sourceSite))
                },
                onContinueWatching = { entry ->
                    navController.navigate(
                        Player(
                            episodeId = entry.episodeId,
                            site = entry.sourceSite,
                            title = "${entry.animeTitle} - EP ${entry.episodeNumber}",
                            animeId = entry.animeId,
                            animeSlug = entry.animeSlug,
                            animeTitle = entry.animeTitle,
                            coverUrl = entry.coverUrl ?: "",
                            episodeNumber = entry.episodeNumber,
                        )
                    )
                },
                onSettingsClick = { navController.navigate(Settings) },
            )
        }

        composable<Detail> { backStackEntry ->
            val route = backStackEntry.toRoute<Detail>()
            DetailScreen(
                animeId = route.animeId,
                slug = route.slug,
                site = route.site,
                onPlayEpisode = { episodeId, epNumber, epTitle, coverUrl, _, _, _, _ ->
                    navController.navigate(
                        Player(
                            episodeId = episodeId,
                            site = route.site,
                            title = epTitle,
                            animeId = route.animeId,
                            animeSlug = route.slug,
                            animeTitle = route.slug,
                            coverUrl = coverUrl ?: "",
                            episodeNumber = epNumber,
                        )
                    )
                },
                onBack = { navController.popBackStack() },
            )
        }

        composable<Player> { backStackEntry ->
            val route = backStackEntry.toRoute<Player>()
            PlayerScreen(
                episodeId = route.episodeId,
                site = route.site,
                title = route.title,
                animeId = route.animeId,
                animeSlug = route.animeSlug,
                animeTitle = route.animeTitle,
                coverUrl = route.coverUrl,
                episodeNumber = route.episodeNumber,
                onBack = { navController.popBackStack() },
                onNavigateToEpisode = { nextId, nextNum ->
                    navController.navigate(
                        route.copy(
                            episodeId = nextId,
                            episodeNumber = nextNum,
                            title = "${route.animeTitle} - EP $nextNum",
                        )
                    ) {
                        popUpTo<Player> { inclusive = true }
                    }
                },
            )
        }

        composable<Settings> {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
    }
}
