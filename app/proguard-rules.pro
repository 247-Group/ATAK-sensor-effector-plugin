# RACK Sensor/Effector ATAK Plugin ProGuard Rules

# Keep ATAK plugin lifecycle
-keep class com.group247.ataksensoreffector.plugin.** { *; }

# Keep data models for Gson serialization
-keep class com.group247.ataksensoreffector.model.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# Gson
-keep class com.google.gson.** { *; }
-keepattributes Signature
-keepattributes *Annotation*
