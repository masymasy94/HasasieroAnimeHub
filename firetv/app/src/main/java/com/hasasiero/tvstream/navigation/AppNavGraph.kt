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
data class Player(val episodeId: Int, val site: String, val title: String)

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
                onSettingsClick = { navController.navigate(Settings) },
            )
        }

        composable<Detail> { backStackEntry ->
            val route = backStackEntry.toRoute<Detail>()
            DetailScreen(
                animeId = route.animeId,
                slug = route.slug,
                site = route.site,
                onPlayEpisode = { episodeId, epTitle ->
                    navController.navigate(Player(episodeId, route.site, epTitle))
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
                onBack = { navController.popBackStack() },
            )
        }

        composable<Settings> {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
    }
}
