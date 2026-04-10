# Retrofit
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.hasasiero.tvstream.data.remote.dto.** { *; }

# Kotlin Serialization
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keep,includedescriptorclasses class com.hasasiero.tvstream.**$$serializer { *; }
-keepclassmembers class com.hasasiero.tvstream.** {
    *** Companion;
}
