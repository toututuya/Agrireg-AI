package com.sc.pesticideknowledgemappingsystem.service;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GraphExploreServiceTest {
    @Test
    void tiesAtBestRankRequireClarification() {
        assertEquals(Arrays.asList("Example A（Crop）", "Example B（Disease）"),
                GraphExploreService.competingNames(Arrays.asList(
                        match("Example A", "Crop", 2),
                        match("Example B", "Disease", 2),
                        match("Lower match", "Crop", 3))));
    }

    @Test
    void aBetterExactMatchDoesNotRequestClarification() {
        assertTrue(GraphExploreService.competingNames(Arrays.asList(
                match("Example A", "Crop", 0),
                match("Longer Example A", "Crop", 2))).isEmpty());
    }

    private Map<String, Object> match(String name, String label, long rank) {
        Map<String, Object> match = new LinkedHashMap<>();
        match.put("name", name);
        match.put("label", label);
        match.put("matchRank", rank);
        return match;
    }
}
