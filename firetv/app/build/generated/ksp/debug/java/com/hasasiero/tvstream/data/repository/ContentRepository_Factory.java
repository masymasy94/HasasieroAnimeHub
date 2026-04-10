package com.hasasiero.tvstream.data.repository;

import com.hasasiero.tvstream.data.remote.ApiService;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata("javax.inject.Singleton")
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
public final class ContentRepository_Factory implements Factory<ContentRepository> {
  private final Provider<ApiService> apiProvider;

  public ContentRepository_Factory(Provider<ApiService> apiProvider) {
    this.apiProvider = apiProvider;
  }

  @Override
  public ContentRepository get() {
    return newInstance(apiProvider.get());
  }

  public static ContentRepository_Factory create(Provider<ApiService> apiProvider) {
    return new ContentRepository_Factory(apiProvider);
  }

  public static ContentRepository newInstance(ApiService api) {
    return new ContentRepository(api);
  }
}
