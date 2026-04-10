package com.hasasiero.tvstream.ui.player;

import com.hasasiero.tvstream.data.remote.ServerConfig;
import com.hasasiero.tvstream.data.repository.ContentRepository;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata
@QualifierMetadata
@DaggerGenerated
@Generated(
    value = "dagger.internal.codegen.ComponentProcessor",
    comments = "https://dagger.dev"
)
@SuppressWarnings({
    "unchecked",
    "rawtypes",
    "KotlinInternal",
    "KotlinInternalInJava",
    "cast"
})
public final class PlayerViewModel_Factory implements Factory<PlayerViewModel> {
  private final Provider<ContentRepository> repositoryProvider;

  private final Provider<ServerConfig> serverConfigProvider;

  public PlayerViewModel_Factory(Provider<ContentRepository> repositoryProvider,
      Provider<ServerConfig> serverConfigProvider) {
    this.repositoryProvider = repositoryProvider;
    this.serverConfigProvider = serverConfigProvider;
  }

  @Override
  public PlayerViewModel get() {
    return newInstance(repositoryProvider.get(), serverConfigProvider.get());
  }

  public static PlayerViewModel_Factory create(Provider<ContentRepository> repositoryProvider,
      Provider<ServerConfig> serverConfigProvider) {
    return new PlayerViewModel_Factory(repositoryProvider, serverConfigProvider);
  }

  public static PlayerViewModel newInstance(ContentRepository repository,
      ServerConfig serverConfig) {
    return new PlayerViewModel(repository, serverConfig);
  }
}
