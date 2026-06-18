package com.group247.ataksensoreffector.plugin;

import android.content.Context;
import com.atakmap.android.maps.MapView;
import com.atakmap.android.dropdown.DropDownMapComponent;

public class SensorEffectorLifecycle extends DropDownMapComponent {

    private static final String TAG = "SensorEffectorLifecycle";

    @Override
    public void onCreate(Context context, android.content.Intent intent, MapView view) {
        super.onCreate(context, intent, view);
    }

    @Override
    protected void onDestroyImpl(Context context, MapView view) {
        super.onDestroyImpl(context, view);
    }
}
