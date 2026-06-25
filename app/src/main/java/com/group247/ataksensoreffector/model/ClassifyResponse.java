package com.group247.ataksensoreffector.model;

import com.google.gson.annotations.SerializedName;

/**
 * Response from RACK server /api/classify endpoint.
 */
public class ClassifyResponse {

    @SerializedName("threat_class")
    private String threatClass;

    @SerializedName("threat_score")
    private double threatScore;

    private String model;

    @SerializedName("latency_ms")
    private int latencyMs;

    private String note;

    public String getThreatClass() { return threatClass; }
    public double getThreatScore() { return threatScore; }
    public String getModel() { return model; }
    public int getLatencyMs() { return latencyMs; }
    public String getNote() { return note; }
}
