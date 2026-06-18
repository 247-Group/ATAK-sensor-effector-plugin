package com.group247.ataksensoreffector;

import org.junit.Test;
import static org.junit.Assert.*;

public class PluginTest {

    @Test
    public void pluginPackage_isCorrect() {
        assertEquals("com.group247.ataksensoreffector",
                PluginTest.class.getPackage().getName());
    }
}
