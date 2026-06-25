package com.group247.ataksensoreffector.network;

import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Binder;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import com.group247.ataksensoreffector.model.CapabilityManifest;
import com.group247.ataksensoreffector.model.ThreatEvent;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Background service maintaining persistent connection to the RACK FP server.
 *
 * Responsibilities:
 * - Maintains WebSocket connection for real-time threat event streaming
 * - Handles automatic reconnection on connection loss
 * - Buffers events during disconnection for later transmission
 * - Registers capability manifest on connection
 * - Provides event callbacks to UI components
 */
public class RackConnectionService extends Service implements RackApiClient.EventListener {

    private static final String TAG = "RackConnectionService";
    private static final String PREFS_NAME = "rack_settings";
    private static final long RECONNECT_DELAY_MS = 5000;
    private static final int MAX_BUFFER_SIZE = 1000;

    private final IBinder binder = new LocalBinder();
    private RackApiClient apiClient;
    private ExecutorService executor;
    private Handler mainHandler;
    private volatile boolean isConnected = false;
    private volatile boolean destroyed = false;
    private final List<ThreatEvent> eventBuffer = new ArrayList<>();
    private final java.util.concurrent.CopyOnWriteArrayList<ThreatEventCallback> callbacks = new java.util.concurrent.CopyOnWriteArrayList<>();

    public interface ThreatEventCallback {
        void onThreatEvent(ThreatEvent event);
        void onConnectionChanged(boolean connected);
    }

    public class LocalBinder extends Binder {
        public RackConnectionService getService() {
            return RackConnectionService.this;
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        executor = Executors.newFixedThreadPool(2);
        mainHandler = new Handler(Looper.getMainLooper());

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String host = prefs.getString("rack_host", "10.247.4.3");
        int port = prefs.getInt("rack_port", 8790);

        apiClient = new RackApiClient(host, port);
        Log.i(TAG, "RACK Connection Service created: " + apiClient.getBaseUrl());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        connect();
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public void onDestroy() {
        destroyed = true;
        mainHandler.removeCallbacksAndMessages(null);
        disconnect();
        executor.shutdown();
        super.onDestroy();
    }

    // -------------------------------------------------------------------------
    // Connection Management
    // -------------------------------------------------------------------------

    public void connect() {
        executor.submit(() -> {
            Log.i(TAG, "Connecting to RACK server...");
            if (apiClient.checkHealth()) {
                Log.i(TAG, "RACK server is healthy, connecting WebSocket");
                registerManifest();
                apiClient.connectWebSocket(this);
            } else {
                Log.w(TAG, "RACK server unreachable, scheduling reconnect");
                scheduleReconnect();
            }
        });
    }

    public void disconnect() {
        apiClient.shutdown();
        isConnected = false;
        notifyConnectionChanged(false);
    }

    public void updateServerAddress(String host, int port) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit()
            .putString("rack_host", host)
            .putInt("rack_port", port)
            .apply();

        disconnect();
        apiClient = new RackApiClient(host, port);
        connect();
    }

    private void scheduleReconnect() {
        if (destroyed) return;
        mainHandler.postDelayed(this::connect, RECONNECT_DELAY_MS);
    }

    private void registerManifest() {
        try {
            CapabilityManifest manifest = CapabilityManifest.createDefault();
            apiClient.registerManifest(manifest);
            Log.i(TAG, "Capability manifest registered with RACK server");
        } catch (IOException e) {
            Log.e(TAG, "Failed to register manifest", e);
        }
    }

    // -------------------------------------------------------------------------
    // Event Submission
    // -------------------------------------------------------------------------

    /**
     * Submit a ThreatEvent to the RACK server for ingestion.
     * If disconnected, the event is buffered for later transmission.
     */
    public void submitEvent(ThreatEvent event) {
        executor.submit(() -> {
            if (isConnected) {
                try {
                    apiClient.ingestEvent(event);
                    flushBuffer();
                } catch (IOException e) {
                    Log.e(TAG, "Failed to submit event, buffering", e);
                    bufferEvent(event);
                }
            } else {
                bufferEvent(event);
            }
        });
    }

    private void bufferEvent(ThreatEvent event) {
        synchronized (eventBuffer) {
            if (eventBuffer.size() >= MAX_BUFFER_SIZE) {
                eventBuffer.remove(0);
            }
            eventBuffer.add(event);
        }
    }

    private void flushBuffer() {
        synchronized (eventBuffer) {
            if (eventBuffer.isEmpty()) return;
            try {
                apiClient.ingestBatch(new ArrayList<>(eventBuffer));
                eventBuffer.clear();
                Log.i(TAG, "Flushed event buffer");
            } catch (IOException e) {
                Log.w(TAG, "Buffer flush failed, will retry", e);
            }
        }
    }

    // -------------------------------------------------------------------------
    // RackApiClient.EventListener
    // -------------------------------------------------------------------------

    @Override
    public void onThreatEvent(ThreatEvent event) {
        mainHandler.post(() -> {
            for (ThreatEventCallback cb : callbacks) {
                cb.onThreatEvent(event);
            }
        });
    }

    @Override
    public void onConnectionStateChanged(boolean connected) {
        isConnected = connected;
        if (connected) {
            flushBuffer();
        } else {
            scheduleReconnect();
        }
        notifyConnectionChanged(connected);
    }

    @Override
    public void onError(String message) {
        Log.e(TAG, "RACK API error: " + message);
    }

    // -------------------------------------------------------------------------
    // Callbacks
    // -------------------------------------------------------------------------

    public void registerCallback(ThreatEventCallback callback) {
        callbacks.add(callback);
    }

    public void unregisterCallback(ThreatEventCallback callback) {
        callbacks.remove(callback);
    }

    private void notifyConnectionChanged(boolean connected) {
        mainHandler.post(() -> {
            for (ThreatEventCallback cb : callbacks) {
                cb.onConnectionChanged(connected);
            }
        });
    }

    // -------------------------------------------------------------------------
    // Accessors
    // -------------------------------------------------------------------------

    public boolean isConnected() {
        return isConnected;
    }

    public RackApiClient getApiClient() {
        return apiClient;
    }

    public int getBufferSize() {
        synchronized (eventBuffer) {
            return eventBuffer.size();
        }
    }
}
