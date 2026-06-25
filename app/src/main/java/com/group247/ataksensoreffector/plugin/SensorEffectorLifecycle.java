package com.group247.ataksensoreffector.plugin;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import com.group247.ataksensoreffector.network.RackConnectionService;

/**
 * ATAK Plugin Lifecycle Receiver.
 *
 * This receiver is invoked by ATAK when the plugin is loaded/unloaded.
 * It starts/stops the RackConnectionService for backend communication.
 *
 * When the ATAK SDK JAR is added to app/libs/, this should be upgraded to
 * extend AbstractPluginLifecycle and register a DropDownMapComponent for
 * full ATAK map integration (threat markers, sensor overlays, etc.).
 *
 * Current capabilities (without ATAK SDK):
 * - Starts background RACK connection service
 * - Registers capability manifest with RACK server
 * - Receives real-time threat events via WebSocket
 * - Buffers events during disconnection
 *
 * Sprint 2 capabilities (with ATAK SDK):
 * - DropDownMapComponent with threat feed panel
 * - CoT marker injection for classified threats
 * - Sensor coverage overlays on ATAK map
 * - Effector action dispatch (slew camera, redirect UAS, etc.)
 */
public class SensorEffectorLifecycle extends BroadcastReceiver {

    private static final String TAG = "SensorEffectorLifecycle";
    private static final String ACTION_PLUGIN = "com.atakmap.app.PLUGIN";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) {
            return;
        }

        String action = intent.getAction();
        Log.i(TAG, "Plugin lifecycle event: " + action);

        if (ACTION_PLUGIN.equals(action)) {
            // Start the RACK connection service
            Intent serviceIntent = new Intent(context, RackConnectionService.class);
            context.startService(serviceIntent);
            Log.i(TAG, "RACK Connection Service started");
        }
    }
}
