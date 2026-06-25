package com.group247.ataksensoreffector.network;

import android.util.Log;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;
import com.group247.ataksensoreffector.model.CapabilityManifest;
import com.group247.ataksensoreffector.model.ClassifyResponse;
import com.group247.ataksensoreffector.model.ThreatEvent;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * HTTP/WebSocket client for the RACK FP API server.
 *
 * Handles:
 * - Health checks and connectivity monitoring
 * - ThreatEvent ingestion (single and batch)
 * - CapabilityManifest registration
 * - Threat classification requests
 * - Real-time WebSocket event streaming
 */
public class RackApiClient {

    private static final String TAG = "RackApiClient";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient;
    private final Gson gson;
    private String baseUrl;
    private WebSocket webSocket;

    public interface EventListener {
        void onThreatEvent(ThreatEvent event);
        void onConnectionStateChanged(boolean connected);
        void onError(String message);
    }

    public RackApiClient(String host, int port) {
        this.baseUrl = String.format("http://%s:%d", host, port);
        this.gson = new Gson();
        this.httpClient = new OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();
    }

    public void setBaseUrl(String host, int port) {
        this.baseUrl = String.format("http://%s:%d", host, port);
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    // -------------------------------------------------------------------------
    // Health & Status
    // -------------------------------------------------------------------------

    /**
     * Check server health. Returns true if server is reachable and healthy.
     */
    public boolean checkHealth() {
        try {
            Request request = new Request.Builder()
                .url(baseUrl + "/api/health")
                .get()
                .build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    JsonObject json = JsonParser.parseString(response.body().string()).getAsJsonObject();
                    return "ok".equals(json.get("status").getAsString());
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "Health check failed: " + e.getMessage());
        }
        return false;
    }

    /**
     * Get dataset statistics from the server.
     */
    public JsonObject getStats() throws IOException {
        Request request = new Request.Builder()
            .url(baseUrl + "/api/stats")
            .get()
            .build();
        try (Response response = httpClient.newCall(request).execute()) {
            if (response.isSuccessful() && response.body() != null) {
                return JsonParser.parseString(response.body().string()).getAsJsonObject();
            }
            throw new IOException("Stats request failed: " + response.code());
        }
    }

    // -------------------------------------------------------------------------
    // Event Ingestion
    // -------------------------------------------------------------------------

    /**
     * Ingest a single ThreatEvent into the RACK server.
     */
    public JsonObject ingestEvent(ThreatEvent event) throws IOException {
        String json = gson.toJson(event);
        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
            .url(baseUrl + "/api/events")
            .post(body)
            .build();
        try (Response response = httpClient.newCall(request).execute()) {
            if (response.body() != null) {
                return JsonParser.parseString(response.body().string()).getAsJsonObject();
            }
            throw new IOException("Ingest failed: " + response.code());
        }
    }

    /**
     * Ingest a batch of ThreatEvents.
     */
    public JsonObject ingestBatch(List<ThreatEvent> events) throws IOException {
        String json = gson.toJson(events);
        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
            .url(baseUrl + "/api/events/batch")
            .post(body)
            .build();
        try (Response response = httpClient.newCall(request).execute()) {
            if (response.body() != null) {
                return JsonParser.parseString(response.body().string()).getAsJsonObject();
            }
            throw new IOException("Batch ingest failed: " + response.code());
        }
    }

    // -------------------------------------------------------------------------
    // Classification
    // -------------------------------------------------------------------------

    /**
     * Classify a ThreatEvent using the server's model.
     */
    public ClassifyResponse classify(ThreatEvent event) throws IOException {
        String json = gson.toJson(event);
        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
            .url(baseUrl + "/api/classify")
            .post(body)
            .build();
        try (Response response = httpClient.newCall(request).execute()) {
            if (response.isSuccessful() && response.body() != null) {
                return gson.fromJson(response.body().string(), ClassifyResponse.class);
            }
            throw new IOException("Classify failed: " + response.code());
        }
    }

    // -------------------------------------------------------------------------
    // Manifest Registration
    // -------------------------------------------------------------------------

    /**
     * Register this plugin's capability manifest with the RACK server.
     */
    public JsonObject registerManifest(CapabilityManifest manifest) throws IOException {
        String json = gson.toJson(manifest);
        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
            .url(baseUrl + "/api/manifests")
            .post(body)
            .build();
        try (Response response = httpClient.newCall(request).execute()) {
            if (response.body() != null) {
                return JsonParser.parseString(response.body().string()).getAsJsonObject();
            }
            throw new IOException("Manifest registration failed: " + response.code());
        }
    }

    // -------------------------------------------------------------------------
    // WebSocket Streaming
    // -------------------------------------------------------------------------

    /**
     * Connect to the RACK server's WebSocket for real-time event streaming.
     */
    public void connectWebSocket(EventListener listener) {
        String wsUrl = baseUrl.replace("http://", "ws://") + "/api/ws/events";
        Request request = new Request.Builder().url(wsUrl).build();

        webSocket = httpClient.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response response) {
                Log.i(TAG, "WebSocket connected to RACK server");
                listener.onConnectionStateChanged(true);
            }

            @Override
            public void onMessage(WebSocket ws, String text) {
                try {
                    JsonObject msg = JsonParser.parseString(text).getAsJsonObject();
                    String type = msg.has("type") ? msg.get("type").getAsString() : "";
                    if ("event".equals(type) && msg.has("data")) {
                        ThreatEvent event = gson.fromJson(msg.get("data"), ThreatEvent.class);
                        listener.onThreatEvent(event);
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Error parsing WebSocket message", e);
                    listener.onError("Parse error: " + e.getMessage());
                }
            }

            @Override
            public void onClosing(WebSocket ws, int code, String reason) {
                ws.close(1000, null);
                listener.onConnectionStateChanged(false);
            }

            @Override
            public void onFailure(WebSocket ws, Throwable t, Response response) {
                Log.e(TAG, "WebSocket failure", t);
                listener.onConnectionStateChanged(false);
                listener.onError("WebSocket: " + t.getMessage());
            }
        });
    }

    /**
     * Disconnect the WebSocket.
     */
    public void disconnectWebSocket() {
        if (webSocket != null) {
            webSocket.close(1000, "Plugin closing");
            webSocket = null;
        }
    }

    /**
     * Send a ping over the WebSocket to keep connection alive.
     */
    public void sendPing() {
        if (webSocket != null) {
            webSocket.send("{\"type\":\"ping\"}");
        }
    }

    /**
     * Shutdown the HTTP client and close all connections.
     */
    public void shutdown() {
        disconnectWebSocket();
        httpClient.dispatcher().executorService().shutdown();
        httpClient.connectionPool().evictAll();
    }
}
