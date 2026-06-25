package com.group247.ataksensoreffector.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

/**
 * CapabilityManifest for registering this plugin's capabilities with the RACK server.
 * Maps to schemas/capability_manifest.schema.json.
 */
public class CapabilityManifest {

    @SerializedName("plugin_id")
    private String pluginId;

    private String version;
    private String description;

    @SerializedName("available_actions")
    private List<Action> availableActions;

    public static class Action {
        @SerializedName("action_id")
        private String actionId;

        private String description;

        @SerializedName("requires_human_gate")
        private boolean requiresHumanGate;

        public Action(String actionId, String description, boolean requiresHumanGate) {
            this.actionId = actionId;
            this.description = description;
            this.requiresHumanGate = requiresHumanGate;
        }

        public String getActionId() { return actionId; }
        public String getDescription() { return description; }
        public boolean isRequiresHumanGate() { return requiresHumanGate; }
    }

    public CapabilityManifest(String pluginId, String version, String description, List<Action> actions) {
        this.pluginId = pluginId;
        this.version = version;
        this.description = description;
        this.availableActions = actions;
    }

    public String getPluginId() { return pluginId; }
    public String getVersion() { return version; }
    public String getDescription() { return description; }
    public List<Action> getAvailableActions() { return availableActions; }

    /**
     * Create the default manifest for the ATAK Sensor/Effector plugin.
     */
    public static CapabilityManifest createDefault() {
        return new CapabilityManifest(
            "atak-sensor-effector-v1",
            "1.0.0",
            "ATAK plugin for RACK FP sensor data collection and effector command execution",
            List.of(
                new Action("issue_fp_alert", "Display force protection alert on ATAK map", false),
                new Action("slew_camera", "Slew PTZ camera to threat bearing", false),
                new Action("redirect_uas", "Redirect friendly UAS to investigate threat", true),
                new Action("escalate_fpcon", "Escalate Force Protection Condition level", true),
                new Action("generate_coa", "Generate Course of Action recommendation", false),
                new Action("mark_threat", "Place threat marker on ATAK shared map", false),
                new Action("send_9line", "Generate and send 9-line threat report via CoT", false)
            )
        );
    }
}
