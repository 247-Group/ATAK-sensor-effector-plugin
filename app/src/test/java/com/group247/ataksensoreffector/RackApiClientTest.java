package com.group247.ataksensoreffector;

import com.group247.ataksensoreffector.network.RackApiClient;

import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;

public class RackApiClientTest {

    private RackApiClient client;

    @Before
    public void setUp() {
        client = new RackApiClient("localhost", 8790);
    }

    @Test
    public void baseUrl_formatsCorrectly() {
        assertEquals("http://localhost:8790", client.getBaseUrl());
    }

    @Test
    public void setBaseUrl_updatesEndpoint() {
        client.setBaseUrl("10.247.4.3", 9000);
        assertEquals("http://10.247.4.3:9000", client.getBaseUrl());
    }

    @Test
    public void healthCheck_returnsfalse_whenServerDown() {
        // Server is not running, health check should return false (not throw)
        assertFalse(client.checkHealth());
    }
}
