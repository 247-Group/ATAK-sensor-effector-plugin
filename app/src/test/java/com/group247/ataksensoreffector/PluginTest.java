package com.group247.ataksensoreffector;

import com.group247.ataksensoreffector.model.CapabilityManifest;
import com.group247.ataksensoreffector.model.ThreatEvent;
import com.group247.ataksensoreffector.plugin.SensorEffectorLifecycle;

import org.junit.Test;
import static org.junit.Assert.*;

import android.content.BroadcastReceiver;

public class PluginTest {

    @Test
    public void pluginPackage_isCorrect() {
        assertEquals("com.group247.ataksensoreffector",
                PluginTest.class.getPackage().getName());
    }

    @Test
    public void lifecycle_isBroadcastReceiver() {
        assertTrue("SensorEffectorLifecycle must extend BroadcastReceiver",
                BroadcastReceiver.class.isAssignableFrom(SensorEffectorLifecycle.class));
    }

    @Test
    public void threatEvent_cotXml_containsRequiredFields() {
        ThreatEvent event = new ThreatEvent();
        event.setEventId("test-001");
        event.setLat(13.5839);
        event.setLon(144.9247);
        event.setAltitudeMagl(50.0);
        event.setHeadingDeg(180.0);
        event.setVelocityMps(12.5);
        event.setThreatClass("air_uas_small");
        event.setThreatScore(0.78);
        event.setSensorId("ECHODYNE-01");
        event.setDetectionZone("NORTH-PERIMETER");
        event.setTimestampUtc("2026-06-24T12:00:00Z");
        event.setCotType("a-h-A-M-F-Q");

        String cot = event.toCotXml();
        assertNotNull(cot);
        assertTrue("CoT must contain event uid", cot.contains("uid='RACK-test-001'"));
        assertTrue("CoT must contain point lat", cot.contains("lat='13.583900'"));
        assertTrue("CoT must contain point lon", cot.contains("lon='144.924700'"));
        assertTrue("CoT must contain threat class", cot.contains("air_uas_small"));
        assertTrue("CoT must contain sensor id", cot.contains("ECHODYNE-01"));
        assertTrue("CoT must contain cot_type", cot.contains("type='a-h-A-M-F-Q'"));
    }

    @Test
    public void threatEvent_toString_formatsCorrectly() {
        ThreatEvent event = new ThreatEvent();
        event.setEventId("evt-123");
        event.setThreatClass("ground_vehicle");
        event.setThreatScore(0.80);
        event.setSensorId("MCQ-RANGER-NORTH");

        String str = event.toString();
        assertTrue(str.contains("evt-123"));
        assertTrue(str.contains("ground_vehicle"));
        assertTrue(str.contains("MCQ-RANGER-NORTH"));
    }

    @Test
    public void capabilityManifest_defaultHasCorrectActions() {
        CapabilityManifest manifest = CapabilityManifest.createDefault();
        assertNotNull(manifest);
        assertEquals("atak-sensor-effector-v1", manifest.getPluginId());
        assertEquals("1.0.0", manifest.getVersion());
        assertNotNull(manifest.getAvailableActions());
        assertEquals(7, manifest.getAvailableActions().size());

        // Verify human gate is required for escalation actions
        boolean foundEscalate = false;
        boolean foundRedirect = false;
        for (CapabilityManifest.Action action : manifest.getAvailableActions()) {
            if ("escalate_fpcon".equals(action.getActionId())) {
                assertTrue("FPCON escalation must require human gate", action.isRequiresHumanGate());
                foundEscalate = true;
            }
            if ("redirect_uas".equals(action.getActionId())) {
                assertTrue("UAS redirect must require human gate", action.isRequiresHumanGate());
                foundRedirect = true;
            }
        }
        assertTrue("Must have escalate_fpcon action", foundEscalate);
        assertTrue("Must have redirect_uas action", foundRedirect);
    }

    @Test
    public void threatEvent_settersAndGetters() {
        ThreatEvent e = new ThreatEvent();
        e.setBearingDeg(45.0);
        e.setRangeM(1500.0);
        e.setRadarCrossSectionM2(0.015);
        e.setTrackConfidence(0.85);
        e.setTrackAgeS(30.0);

        assertEquals(45.0, e.getBearingDeg(), 0.001);
        assertEquals(1500.0, e.getRangeM(), 0.001);
        assertEquals(0.015, e.getRadarCrossSectionM2(), 0.0001);
        assertEquals(0.85, e.getTrackConfidence(), 0.001);
        assertEquals(30.0, e.getTrackAgeS(), 0.001);
    }
}
