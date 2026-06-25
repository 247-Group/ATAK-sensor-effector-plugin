package com.group247.ataksensoreffector.model;

import com.google.gson.annotations.SerializedName;

/**
 * ThreatEvent data model matching the RACK FP JSON schema.
 * Maps to schemas/threat_event.schema.json.
 */
public class ThreatEvent {

    @SerializedName("event_id")
    private String eventId;

    @SerializedName("sensor_id")
    private String sensorId;

    @SerializedName("sensor_type")
    private String sensorType;

    @SerializedName("track_id")
    private String trackId;

    @SerializedName("bearing_deg")
    private double bearingDeg;

    @SerializedName("range_m")
    private double rangeM;

    @SerializedName("altitude_m_agl")
    private double altitudeMagl;

    @SerializedName("velocity_mps")
    private double velocityMps;

    @SerializedName("heading_deg")
    private double headingDeg;

    @SerializedName("radar_cross_section_m2")
    private double radarCrossSectionM2;

    @SerializedName("track_age_s")
    private double trackAgeS;

    @SerializedName("track_confidence_0_1")
    private double trackConfidence;

    @SerializedName("timestamp_utc")
    private String timestampUtc;

    @SerializedName("raw_payload")
    private Object rawPayload;

    @SerializedName("threat_class")
    private String threatClass;

    @SerializedName("threat_score")
    private double threatScore;

    @SerializedName("lat")
    private double lat;

    @SerializedName("lon")
    private double lon;

    @SerializedName("elevation_deg")
    private double elevationDeg;

    @SerializedName("cot_type")
    private String cotType;

    @SerializedName("sensor_modality")
    private String sensorModality;

    @SerializedName("detection_zone")
    private String detectionZone;

    @SerializedName("frequency_mhz")
    private double frequencyMhz;

    @SerializedName("signal_strength_dbm")
    private Double signalStrengthDbm;

    // Getters
    public String getEventId() { return eventId; }
    public String getSensorId() { return sensorId; }
    public String getSensorType() { return sensorType; }
    public String getTrackId() { return trackId; }
    public double getBearingDeg() { return bearingDeg; }
    public double getRangeM() { return rangeM; }
    public double getAltitudeMagl() { return altitudeMagl; }
    public double getVelocityMps() { return velocityMps; }
    public double getHeadingDeg() { return headingDeg; }
    public double getRadarCrossSectionM2() { return radarCrossSectionM2; }
    public double getTrackAgeS() { return trackAgeS; }
    public double getTrackConfidence() { return trackConfidence; }
    public String getTimestampUtc() { return timestampUtc; }
    public String getThreatClass() { return threatClass; }
    public double getThreatScore() { return threatScore; }
    public double getLat() { return lat; }
    public double getLon() { return lon; }
    public String getCotType() { return cotType; }
    public String getSensorModality() { return sensorModality; }
    public String getDetectionZone() { return detectionZone; }

    // Setters
    public void setEventId(String eventId) { this.eventId = eventId; }
    public void setSensorId(String sensorId) { this.sensorId = sensorId; }
    public void setSensorType(String sensorType) { this.sensorType = sensorType; }
    public void setTrackId(String trackId) { this.trackId = trackId; }
    public void setBearingDeg(double bearingDeg) { this.bearingDeg = bearingDeg; }
    public void setRangeM(double rangeM) { this.rangeM = rangeM; }
    public void setAltitudeMagl(double altitudeMagl) { this.altitudeMagl = altitudeMagl; }
    public void setVelocityMps(double velocityMps) { this.velocityMps = velocityMps; }
    public void setHeadingDeg(double headingDeg) { this.headingDeg = headingDeg; }
    public void setRadarCrossSectionM2(double rcs) { this.radarCrossSectionM2 = rcs; }
    public void setTrackAgeS(double trackAgeS) { this.trackAgeS = trackAgeS; }
    public void setTrackConfidence(double trackConfidence) { this.trackConfidence = trackConfidence; }
    public void setTimestampUtc(String timestampUtc) { this.timestampUtc = timestampUtc; }
    public void setThreatClass(String threatClass) { this.threatClass = threatClass; }
    public void setThreatScore(double threatScore) { this.threatScore = threatScore; }
    public void setLat(double lat) { this.lat = lat; }
    public void setLon(double lon) { this.lon = lon; }
    public void setCotType(String cotType) { this.cotType = cotType; }
    public void setSensorModality(String sensorModality) { this.sensorModality = sensorModality; }
    public void setDetectionZone(String detectionZone) { this.detectionZone = detectionZone; }

    /**
     * Build a CoT (Cursor on Target) XML string for this event.
     * Used to inject threat markers into the ATAK map view.
     */
    public String toCotXml() {
        String how = "m-g";  // machine-generated
        String type = escapeXml(cotType != null ? cotType : "a-u-G");
        String safeEventId = escapeXml(eventId != null ? eventId : "unknown");
        String safeTimestamp = escapeXml(timestampUtc != null ? timestampUtc : "");
        String safeThreatClass = escapeXml(threatClass != null ? threatClass : "unknown");
        String safeSensorId = escapeXml(sensorId != null ? sensorId : "unknown");
        String safeZone = escapeXml(detectionZone != null ? detectionZone : "unknown");
        return String.format(
            "<event version='2.0' uid='RACK-%s' type='%s' time='%s' start='%s' stale='%s' how='%s'>"
            + "<point lat='%f' lon='%f' hae='%f' ce='9999999' le='9999999'/>"
            + "<detail>"
            + "<track course='%f' speed='%f'/>"
            + "<remarks>RACK FP: %s (score=%.2f) sensor=%s zone=%s</remarks>"
            + "</detail>"
            + "</event>",
            safeEventId, type, safeTimestamp, safeTimestamp, safeTimestamp, how,
            lat, lon, altitudeMagl,
            headingDeg, velocityMps,
            safeThreatClass, threatScore, safeSensorId, safeZone
        );
    }

    private static String escapeXml(String input) {
        if (input == null) return "";
        return input.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace("'", "&apos;")
                     .replace("\"", "&quot;");
    }

    @Override
    public String toString() {
        return String.format("ThreatEvent{id=%s, class=%s, score=%.2f, sensor=%s}",
            eventId, threatClass, threatScore, sensorId);
    }
}
